import os
import sys
import argparse
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def setup_logging(level="INFO"):
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "butler.log"),
            logging.StreamHandler()
        ]
    )


def check_dependencies():
    print("检查依赖...")
    
    required_modules = [
        "cv2", "numpy", "sounddevice", "soundfile"
    ]
    
    optional_modules = {
        "openwakeword": "唤醒词检测",
        "faster_whisper": "语音识别",
        "piper": "语音合成",
        "httpx": "HTTP客户端",
        "PIL": "图像处理"
    }
    
    missing_required = []
    missing_optional = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_required.append(module)
    
    for module, desc in optional_modules.items():
        try:
            __import__(module)
        except ImportError:
            missing_optional.append(f"{module} ({desc})")
    
    if missing_required:
        print("❌ 缺少必要依赖:")
        for m in missing_required:
            print(f"   - {m}")
        return False
    
    if missing_optional:
        print("⚠️  缺少可选依赖:")
        for m in missing_optional:
            print(f"   - {m}")
        print("\n部分功能可能无法使用")
    
    print("✅ 依赖检查完成")
    return True


def check_config(config_path="butler/smart_butler_config.json"):
    config_file = Path(config_path)
    
    if not config_file.exists():
        print(f"⚠️  配置文件不存在: {config_path}")
        print("使用默认配置...")
        return None
    
    print(f"✅ 配置文件: {config_path}")
    return str(config_path)


def check_directories():
    directories = [
        "logs",
        "data",
        "models/wakeword",
        "models/tts",
        "models/whisper"
    ]
    
    for dir_path in directories:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    print("✅ 目录结构检查完成")


def start_butler(config_path=None):
    try:
        from butler.core.integrated_butler import IntegratedSmartButler
        
        butler = IntegratedSmartButler(config_path)
        butler.run_forever()
        
    except KeyboardInterrupt:
        print("\n\n程序已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description="启动智能管家系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python start_butler.py                    # 使用默认配置启动
  python start_butler.py -c custom.json     # 使用自定义配置
  python start_butler.py --debug           # 调试模式
  python start_butler.py --check-only      # 仅检查依赖
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        help="配置文件路径",
        default="butler/smart_butler_config.json"
    )
    
    parser.add_argument(
        "-l", "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="日志级别"
    )
    
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="仅检查依赖，不启动程序"
    )
    
    parser.add_argument(
        "--no-dep-check",
        action="store_true",
        help="跳过依赖检查"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="调试模式"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        args.log_level = "DEBUG"
    
    setup_logging(args.log_level)
    
    print("=" * 60)
    print("  🏠 智能管家系统 - Smart Butler")
    print("=" * 60)
    print()
    
    check_directories()
    
    if not args.no_dep_check:
        if not check_dependencies():
            print("\n请安装缺失的依赖:")
            print("pip install -r requirements.txt")
            return 1
        
        if args.check_only:
            return 0
    
    config_path = check_config(args.config)
    
    print()
    print("🚀 启动智能管家...")
    print()
    
    try:
        start_butler(config_path)
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
