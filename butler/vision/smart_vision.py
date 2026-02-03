import cv2
import numpy as np
import time
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
from collections import deque

logger = logging.getLogger(__name__)


class ActivityType(Enum):
    IDLE = "idle"
    SITTING = "sitting"
    STANDING = "standing"
    WALKING = "walking"
    RUNNING = "running"
    WORKING = "working"
    READING = "reading"
    WATCHING_TV = "watching_tv"
    SLEEPING = "sleeping"
    COOKING = "cooking"
    EXERCISING = "exercising"
    USING_PHONE = "using_phone"
    UNKNOWN = "unknown"


@dataclass
class Person:
    person_id: int
    bbox: List[float]
    last_seen: float
    activity: ActivityType = ActivityType.UNKNOWN
    activity_confidence: float = 0.0
    position_history: deque = field(default_factory=lambda: deque(maxlen=30))
    activity_history: deque = field(default_factory=lambda: deque(maxlen=10))
    
    def update_position(self, new_bbox: List[float]):
        center_x = (new_bbox[0] + new_bbox[2]) / 2
        center_y = (new_bbox[1] + new_bbox[3]) / 2
        self.position_history.append((center_x, center_y, time.time()))
        self.last_seen = time.time()
        self.bbox = new_bbox
    
    def get_movement_speed(self) -> float:
        if len(self.position_history) < 2:
            return 0.0
        
        latest = self.position_history[-1]
        earliest = self.position_history[0]
        
        dx = latest[0] - earliest[0]
        dy = latest[1] - earliest[1]
        dt = latest[2] - earliest[2]
        
        if dt < 0.1:
            return 0.0
        
        distance = np.sqrt(dx**2 + dy**2)
        return distance / dt
    
    def get_activity_from_history(self) -> Tuple[ActivityType, float]:
        if len(self.activity_history) < 3:
            return ActivityType.UNKNOWN, 0.0
        
        activity_counts = {}
        for act in self.activity_history:
            activity_counts[act] = activity_counts.get(act, 0) + 1
        
        most_common = max(activity_counts, key=activity_counts.get)
        confidence = activity_counts[most_common] / len(self.activity_history)
        
        return most_common, confidence


@dataclass
class VisionEvent:
    event_type: str
    timestamp: float
    person_id: Optional[int] = None
    activity: Optional[ActivityType] = None
    bbox: Optional[List[float]] = None
    confidence: float = 0.0
    data: Dict[str, Any] = field(default_factory=dict)


class SmartVisionMonitor:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or self._default_config()
        
        self.camera = None
        self.vision_detector = None
        self.is_running = False
        
        self.people: Dict[int, Person] = {}
        self.next_person_id = 1
        self.person_id_timeout = 5.0
        
        self.detection_history: List[VisionEvent] = []
        self.max_history_size = 1000
        
        self.event_callbacks: Dict[str, List[callable]] = {}
        
        self.frame_count = 0
        self.last_detection_time = 0
        self.detection_interval = self.config.get("detect_interval", 0.5)
        
        self._init_detector()
    
    def _default_config(self) -> Dict[str, Any]:
        return {
            "camera_index": 0,
            "detect_interval": 0.5,
            "min_person_confidence": 0.5,
            "min_object_confidence": 0.3,
            "person_id_timeout": 5.0,
            "activity_detection": True,
            "track_people": True,
            "proactive_mode": True,
            "cooldown_seconds": 30
        }
    
    def _init_detector(self):
        try:
            from butler.tools.vision import VisionClient, VisionConfig
            
            config = VisionConfig(
                device="cpu",
                face_model_path="",
                object_model_path="yolov8n.pt",
                face_backend="auto",
                face_match_threshold=0.35,
                face_min_confidence=0.5,
                object_min_confidence=self.config["min_object_confidence"],
                max_faces=5
            )
            
            self.vision_detector = VisionClient(config, db=None)
            logger.info("Vision detector initialized")
        except Exception as e:
            logger.error(f"Failed to init vision detector: {e}")
    
    def open_camera(self):
        try:
            camera_index = self.config["camera_index"]
            self.camera = cv2.VideoCapture(camera_index)
            
            if not self.camera.isOpened():
                logger.error(f"Failed to open camera {camera_index}")
                return False
            
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.camera.set(cv2.CAP_PROP_FPS, 30)
            
            logger.info(f"Camera opened: {camera_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to open camera: {e}")
            return False
    
    def close_camera(self):
        if self.camera:
            self.camera.release()
            self.camera = None
            logger.info("Camera closed")
    
    def _track_people(self, person_detections: List[Dict[str, Any]]) -> List[Person]:
        tracked_people = []
        now = time.time()
        
        active_person_ids = set()
        
        for detection in person_detections:
            bbox = detection.get("bbox", [0, 0, 0, 0])
            center_x = (bbox[0] + bbox[2]) / 2
            center_y = (bbox[1] + bbox[3]) / 2
            
            best_match_id = None
            best_match_distance = float('inf')
            
            for person_id, person in self.people.items():
                if now - person.last_seen > self.person_id_timeout:
                    continue
                
                last_center = person.position_history[-1][:2] if person.position_history else (center_x, center_y)
                distance = np.sqrt((center_x - last_center[0])**2 + (center_y - last_center[1])**2)
                
                if distance < 150 and distance < best_match_distance:
                    best_match_distance = distance
                    best_match_id = person_id
            
            if best_match_id is None:
                best_match_id = self.next_person_id
                self.next_person_id += 1
                self.people[best_match_id] = Person(
                    person_id=best_match_id,
                    bbox=bbox,
                    last_seen=now
                )
            
            person = self.people[best_match_id]
            person.update_position(bbox)
            
            if self.config["activity_detection"]:
                activity, confidence = self._detect_activity(person)
                person.activity = activity
                person.activity_confidence = confidence
                person.activity_history.append(activity)
            
            active_person_ids.add(best_match_id)
            tracked_people.append(person)
        
        self.people = {
            pid: person for pid, person in self.people.items()
            if pid in active_person_ids
        }
        
        return tracked_people
    
    def _detect_activity(self, person: Person) -> Tuple[ActivityType, float]:
        speed = person.get_movement_speed()
        
        if speed > 100:
            return ActivityType.RUNNING, 0.8
        elif speed > 30:
            return ActivityType.WALKING, 0.7
        elif speed < 5:
            bbox_width = person.bbox[2] - person.bbox[0]
            bbox_height = person.bbox[3] - person.bbox[1]
            
            if bbox_height > 300:
                return ActivityType.STANDING, 0.6
            elif bbox_height > 200:
                return ActivityType.SITTING, 0.7
            else:
                return ActivityType.IDLE, 0.5
        
        return ActivityType.UNKNOWN, 0.3
    
    def _detect_nearby_objects(
        self,
        person: Person,
        object_detections: List[Dict[str, Any]]
    ) -> List[str]:
        nearby_objects = []
        person_center_x = (person.bbox[0] + person.bbox[2]) / 2
        person_center_y = (person.bbox[1] + person.bbox[3]) / 2
        
        for obj in object_detections:
            obj_bbox = obj.get("bbox", [0, 0, 0, 0])
            obj_center_x = (obj_bbox[0] + obj_bbox[2]) / 2
            obj_center_y = (obj_bbox[1] + obj_bbox[3]) / 2
            
            distance = np.sqrt(
                (person_center_x - obj_center_x)**2 +
                (person_center_y - obj_center_y)**2
            )
            
            if distance < 150:
                nearby_objects.append(obj.get("label", ""))
        
        return nearby_objects
    
    def _infer_activity_from_objects(
        self,
        person: Person,
        nearby_objects: List[str]
    ) -> ActivityType:
        activity_map = {
            "laptop": ActivityType.WORKING,
            "keyboard": ActivityType.WORKING,
            "mouse": ActivityType.WORKING,
            "book": ActivityType.READING,
            "cell phone": ActivityType.USING_PHONE,
            "tv": ActivityType.WATCHING_TV,
            "remote": ActivityType.WATCHING_TV,
            "bed": ActivityType.SLEEPING,
            "cup": ActivityType.IDLE,
            "bowl": ActivityType.COOKING,
            "knife": ActivityType.COOKING,
        }
        
        for obj in nearby_objects:
            if obj.lower() in activity_map:
                return activity_map[obj.lower()]
        
        return person.activity
    
    def process_frame(self) -> Optional[VisionEvent]:
        if not self.camera or not self.camera.isOpened():
            return None
        
        now = time.time()
        if now - self.last_detection_time < self.detection_interval:
            return None
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                return None
            
            self.frame_count += 1
            self.last_detection_time = now
            
            from PIL import Image
            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            
            result = self.vision_detector.detect(
                img,
                model="object",
                min_conf=self.config["min_object_confidence"],
                max_det=20
            )
            
            if "error" in result:
                return None
            
            detections = result.get("detections", [])
            
            person_detections = [
                det for det in detections
                if det.get("label", "").lower() in ["person", "人"]
                and det.get("confidence", 0) >= self.config["min_person_confidence"]
            ]
            
            object_detections = [
                det for det in detections
                if det.get("label", "").lower() not in ["person", "人"]
            ]
            
            if self.config["track_people"]:
                people = self._track_people(person_detections)
                
                for person in people:
                    nearby_objects = self._detect_nearby_objects(person, object_detections)
                    
                    if nearby_objects:
                        inferred_activity = self._infer_activity_from_objects(person, nearby_objects)
                        person.activity = inferred_activity
                        person.activity_confidence = max(person.activity_confidence, 0.7)
                    
                    event = VisionEvent(
                        event_type="person_activity",
                        timestamp=now,
                        person_id=person.person_id,
                        activity=person.activity,
                        bbox=person.bbox,
                        confidence=person.activity_confidence,
                        data={
                            "nearby_objects": nearby_objects,
                            "movement_speed": person.get_movement_speed()
                        }
                    )
                    
                    self._add_event(event)
                    
                    if self.config["proactive_mode"]:
                        self._trigger_callbacks("activity_detected", event)
                    
                    return event
            
            if object_detections:
                event = VisionEvent(
                    event_type="object_detection",
                    timestamp=now,
                    bbox=object_detections[0].get("bbox"),
                    confidence=object_detections[0].get("confidence", 0),
                    data={"label": object_detections[0].get("label")}
                )
                self._add_event(event)
                
                if self.config["proactive_mode"]:
                    self._trigger_callbacks("object_detected", event)
                
                return event
            
        except Exception as e:
            logger.error(f"Frame processing error: {e}")
        
        return None
    
    def _add_event(self, event: VisionEvent):
        self.detection_history.append(event)
        if len(self.detection_history) > self.max_history_size:
            self.detection_history = self.detection_history[-self.max_history_size:]
    
    def _trigger_callbacks(self, event_type: str, event: VisionEvent):
        if event_type in self.event_callbacks:
            for callback in self.event_callbacks[event_type]:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def register_callback(self, event_type: str, callback: callable):
        if event_type not in self.event_callbacks:
            self.event_callbacks[event_type] = []
        self.event_callbacks[event_type].append(callback)
        logger.info(f"Registered callback for {event_type}")
    
    def unregister_callback(self, event_type: str, callback: callable):
        if event_type in self.event_callbacks:
            if callback in self.event_callbacks[event_type]:
                self.event_callbacks[event_type].remove(callback)
                logger.info(f"Unregistered callback for {event_type}")
    
    def get_recent_events(
        self,
        event_type: Optional[str] = None,
        seconds: float = 60.0
    ) -> List[VisionEvent]:
        now = time.time()
        events = [
            e for e in self.detection_history
            if now - e.timestamp <= seconds
        ]
        
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        
        return events
    
    def get_active_people(self) -> List[Person]:
        now = time.time()
        return [
            person for person in self.people.values()
            if now - person.last_seen < self.person_id_timeout
        ]
    
    def get_activity_summary(self) -> Dict[str, Any]:
        active_people = self.get_active_people()
        
        activity_counts = {}
        for person in active_people:
            activity = person.activity.value
            activity_counts[activity] = activity_counts.get(activity, 0) + 1
        
        return {
            "active_people_count": len(active_people),
            "activities": activity_counts,
            "last_detection_time": self.last_detection_time,
            "frame_count": self.frame_count
        }
    
    def start(self):
        if self.is_running:
            logger.warning("Vision monitor is already running")
            return
        
        if not self.open_camera():
            return False
        
        self.is_running = True
        logger.info("Vision monitor started")
        return True
    
    def stop(self):
        self.is_running = False
        self.close_camera()
        logger.info("Vision monitor stopped")
    
    def run_loop(self):
        if not self.start():
            return
        
        try:
            while self.is_running:
                self.process_frame()
                cv2.waitKey(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()


if __name__ == "__main__":
    def on_activity_detected(event: VisionEvent):
        print(f"Activity detected: {event.activity} (confidence: {event.confidence:.2f})")
    
    def on_object_detected(event: VisionEvent):
        print(f"Object detected: {event.data.get('label')} (confidence: {event.confidence:.2f})")
    
    monitor = SmartVisionMonitor()
    monitor.register_callback("activity_detected", on_activity_detected)
    monitor.register_callback("object_detected", on_object_detected)
    
    monitor.run_loop()
