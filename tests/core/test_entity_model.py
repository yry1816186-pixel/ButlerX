import pytest
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from butler.core.entity_model import (
    Entity, Device, Sensor, User, Location, Service, Automation, Scenario,
    EntityType, EntityDomain, EntityState, EntityStatus
)


class TestEntity:
    def test_entity_creation(self, sample_device_data):
        entity = Entity(
            entity_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            entity_type=EntityType.DEVICE,
            domain=EntityDomain.CONTROL,
            status=EntityStatus.ONLINE
        )
        assert entity.entity_id == sample_device_data["device_id"]
        assert entity.name == sample_device_data["name"]
        assert entity.entity_type == EntityType.DEVICE
        assert entity.status == EntityStatus.ONLINE

    def test_entity_registration(self, sample_device_data):
        entity = Entity(
            entity_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            entity_type=EntityType.DEVICE,
            domain=EntityDomain.CONTROL
        )
        Entity.register(entity)
        registered = Entity.get(sample_device_data["device_id"])
        assert registered is not None
        assert registered.entity_id == sample_device_data["device_id"]
        Entity.unregister(sample_device_data["device_id"])

    def test_entity_get_by_type(self):
        entity1 = Entity(entity_id="dev1", name="Device 1", entity_type=EntityType.DEVICE, domain=EntityDomain.CONTROL)
        entity2 = Entity(entity_id="sen1", name="Sensor 1", entity_type=EntityType.SENSOR, domain=EntityDomain.ENVIRONMENT)
        
        Entity.register(entity1)
        Entity.register(entity2)
        
        devices = Entity.get_by_type(EntityType.DEVICE)
        sensors = Entity.get_by_type(EntityType.SENSOR)
        
        assert entity1 in devices
        assert entity2 in sensors
        assert entity2 not in devices
        
        Entity.unregister("dev1")
        Entity.unregister("sen1")

    def test_entity_get_by_domain(self):
        entity1 = Entity(entity_id="dev1", name="Device 1", entity_type=EntityType.DEVICE, domain=EntityDomain.CONTROL)
        entity2 = Entity(entity_id="dev2", name="Device 2", entity_type=EntityType.DEVICE, domain=EntityDomain.ENVIRONMENT)
        
        Entity.register(entity1)
        Entity.register(entity2)
        
        control_entities = Entity.get_by_domain(EntityDomain.CONTROL)
        env_entities = Entity.get_by_domain(EntityDomain.ENVIRONMENT)
        
        assert entity1 in control_entities
        assert entity2 in env_entities
        assert entity2 not in control_entities
        
        Entity.unregister("dev1")
        Entity.unregister("dev2")

    def test_entity_get_by_location(self):
        entity1 = Entity(entity_id="dev1", name="Device 1", entity_type=EntityType.DEVICE, domain=EntityDomain.CONTROL, location="living_room")
        entity2 = Entity(entity_id="dev2", name="Device 2", entity_type=EntityType.DEVICE, domain=EntityDomain.CONTROL, location="bedroom")
        
        Entity.register(entity1)
        Entity.register(entity2)
        
        living_room_entities = Entity.get_by_location("living_room")
        bedroom_entities = Entity.get_by_location("bedroom")
        
        assert entity1 in living_room_entities
        assert entity2 in bedroom_entities
        assert entity2 not in living_room_entities
        
        Entity.unregister("dev1")
        Entity.unregister("dev2")

    def test_entity_state_change(self, sample_device_data):
        entity = Entity(
            entity_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            entity_type=EntityType.DEVICE,
            domain=EntityDomain.CONTROL
        )
        
        initial_state = entity.state
        entity.set_state(EntityState.ACTIVE)
        assert entity.state == EntityState.ACTIVE
        
        history = entity.get_state_history(limit=1)
        assert len(history) == 1

    def test_entity_status_change(self, sample_device_data):
        entity = Entity(
            entity_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            entity_type=EntityType.DEVICE,
            domain=EntityDomain.CONTROL
        )
        
        assert entity.status == EntityStatus.OFFLINE
        entity.set_status(EntityStatus.ONLINE)
        assert entity.status == EntityStatus.ONLINE

    def test_entity_change_listener(self, sample_device_data):
        callback_called = []
        
        def callback(entity):
            callback_called.append(entity.entity_id)
        
        Entity.add_change_listener(callback)
        
        entity = Entity(
            entity_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            entity_type=EntityType.DEVICE,
            domain=EntityDomain.CONTROL
        )
        Entity.register(entity)
        
        assert sample_device_data["device_id"] in callback_called
        
        Entity.remove_change_listener(callback)
        Entity.unregister(sample_device_data["device_id"])


class TestDevice:
    def test_device_creation(self, sample_device_data):
        device = Device(
            device_id=sample_device_data["device_id"],
            name=sample_device_data["name"],
            device_type=sample_device_data["device_type"],
            domain=EntityDomain.ENVIRONMENT,
            location=sample_device_data["location"],
            manufacturer=sample_device_data["manufacturer"],
            model=sample_device_data["model"],
            version=sample_device_data["version"]
        )
        
        assert device.device_id == sample_device_data["device_id"]
        assert device.device_type == sample_device_data["device_type"]
        assert device.manufacturer == sample_device_data["manufacturer"]
        assert device.model == sample_device_data["model"]

    def test_device_attributes(self):
        device = Device(
            device_id="dev1",
            name="Test Device",
            device_type="light",
            domain=EntityDomain.LIGHTING
        )
        
        device.set_attribute("brightness", 100)
        device.set_attribute("color", "#FF0000")
        
        assert device.get_attribute("brightness") == 100
        assert device.get_attribute("color") == "#FF0000"
        assert device.get_attribute("nonexistent") is None

    def test_device_commands(self):
        device = Device(
            device_id="dev1",
            name="Test Device",
            device_type="light",
            domain=EntityDomain.LIGHTING
        )
        
        async def turn_on(params):
            return {"status": "on"}
        
        device.register_command("turn_on", turn_on)
        assert "turn_on" in device.get_supported_commands()
        assert device.has_command("turn_on")


class TestSensor:
    def test_sensor_creation(self, sample_sensor_data):
        sensor = Sensor(
            sensor_id=sample_sensor_data["sensor_id"],
            name=sample_sensor_data["name"],
            sensor_type=sample_sensor_data["sensor_type"],
            domain=EntityDomain.ENVIRONMENT,
            location=sample_sensor_data["location"],
            unit=sample_sensor_data["unit"]
        )
        
        assert sensor.sensor_id == sample_sensor_data["sensor_id"]
        assert sensor.sensor_type == sample_sensor_data["sensor_type"]
        assert sensor.unit == sample_sensor_data["unit"]

    def test_sensor_value(self):
        sensor = Sensor(
            sensor_id="sen1",
            name="Temperature Sensor",
            sensor_type="temperature",
            domain=EntityDomain.ENVIRONMENT,
            unit="°C"
        )
        
        sensor.set_value(23.5)
        assert sensor.get_value() == 23.5
        assert sensor.get_state().value == 23.5

    def test_sensor_reading_history(self):
        sensor = Sensor(
            sensor_id="sen1",
            name="Temperature Sensor",
            sensor_type="temperature",
            domain=EntityDomain.ENVIRONMENT,
            unit="°C"
        )
        
        sensor.set_value(20.0)
        sensor.set_value(21.0)
        sensor.set_value(22.0)
        
        history = sensor.get_reading_history(limit=2)
        assert len(history) == 2
        assert history[-1].value == 22.0


class TestUser:
    def test_user_creation(self, sample_user_data):
        user = User(
            user_id=sample_user_data["user_id"],
            name=sample_user_data["name"],
            email=sample_user_data["email"],
            role=sample_user_data["role"]
        )
        
        assert user.user_id == sample_user_data["user_id"]
        assert user.name == sample_user_data["name"]
        assert user.email == sample_user_data["email"]
        assert user.role == sample_user_data["role"]

    def test_user_presence(self):
        user = User(
            user_id="user1",
            name="Test User",
            email="test@example.com",
            role="admin"
        )
        
        assert user.is_present() is False
        user.set_present(True)
        assert user.is_present() is True
        user.set_location("living_room")
        assert user.get_location() == "living_room"


class TestLocation:
    def test_location_creation(self, sample_location_data):
        location = Location(
            location_id=sample_location_data["location_id"],
            name=sample_location_data["name"],
            location_type=sample_location_data["type"],
            floor=sample_location_data["floor"]
        )
        
        assert location.location_id == sample_location_data["location_id"]
        assert location.name == sample_location_data["name"]
        assert location.location_type == sample_location_data["type"]
        assert location.floor == sample_location_data["floor"]

    def test_location_areas(self):
        location = Location(
            location_id="loc1",
            name="Living Room",
            location_type="room",
            floor=1
        )
        
        location.add_area("sofa", {"x": 1, "y": 2})
        location.add_area("tv", {"x": 3, "y": 4})
        
        areas = location.get_areas()
        assert len(areas) == 2
        assert "sofa" in areas
        assert "tv" in areas


class TestService:
    def test_service_creation(self, sample_service_data):
        service = Service(
            service_id=sample_service_data["service_id"],
            name=sample_service_data["name"],
            domain=sample_service_data["domain"],
            description=sample_service_data["description"]
        )
        
        assert service.service_id == sample_service_data["service_id"]
        assert service.name == sample_service_data["name"]
        assert service.domain == sample_service_data["domain"]

    def test_service_availability(self):
        service = Service(
            service_id="srv1",
            name="Test Service",
            domain="control",
            description="A test service"
        )
        
        assert service.is_available() is True
        service.set_available(False)
        assert service.is_available() is False


class TestAutomation:
    def test_automation_creation(self, sample_automation_data):
        automation = Automation(
            automation_id=sample_automation_data["automation_id"],
            name=sample_automation_data["name"],
            description=sample_automation_data["description"],
            enabled=sample_automation_data["enabled"]
        )
        
        assert automation.automation_id == sample_automation_data["automation_id"]
        assert automation.name == sample_automation_data["name"]
        assert automation.enabled == sample_automation_data["enabled"]

    def test_automation_execution(self):
        automation = Automation(
            automation_id="auto1",
            name="Test Automation",
            description="A test automation"
        )
        
        assert automation.last_triggered is None
        automation.trigger()
        assert automation.last_triggered is not None
        assert automation.get_trigger_count() > 0


class TestScenario:
    def test_scenario_creation(self, sample_scenario_data):
        scenario = Scenario(
            scenario_id=sample_scenario_data["scenario_id"],
            name=sample_scenario_data["name"],
            scenario_type=sample_scenario_data["scenario_type"]
        )
        
        assert scenario.scenario_id == sample_scenario_data["scenario_id"]
        assert scenario.name == sample_scenario_data["name"]
        assert scenario.scenario_type == sample_scenario_data["scenario_type"]

    def test_scenario_activation(self):
        scenario = Scenario(
            scenario_id="scen1",
            name="Test Scenario",
            scenario_type="manual"
        )
        
        assert scenario.state == EntityState.IDLE
        scenario.activate()
        assert scenario.state == EntityState.ACTIVE
        scenario.deactivate()
        assert scenario.state == EntityState.IDLE
