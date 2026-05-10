import os
import sys
import importlib
from qgis.PyQt.QtWidgets import QMessageBox
from qgis.core import QgsMessageLog, Qgis


def _log(message, level='info'):
    """Log message using QGIS message log"""
    tag = 'DXF-PostGIS-Converter'
    
    if level == 'info':
        QgsMessageLog.logMessage(message, tag, Qgis.Info)
    elif level == 'warning':
        QgsMessageLog.logMessage(message, tag, Qgis.Warning)
    elif level == 'error':
        QgsMessageLog.logMessage(message, tag, Qgis.Critical)
    elif level == 'debug':
        QgsMessageLog.logMessage(f"[DEBUG] {message}", tag, Qgis.Info)


def _install_package(package_name, libs_path=None):
    """
    Install package using pip API directly (not subprocess).
    
    :param package_name: Name of the package to install
    :param libs_path: Optional path to search for local wheels
    :return: True if successful, False otherwise
    """
    try:
        from pip._internal.cli.main import main as pip_main
        
        # Build pip arguments
        args = ['install']
        
        if libs_path and os.path.exists(libs_path):
            args.extend(['--no-index', '--find-links', libs_path])
        
        args.append(package_name)
        
        _log(f"Installing {package_name} with args: {args}", 'debug')
        
        # Call pip main directly
        result = pip_main(args)
        return result == 0
        
    except Exception as e:
        _log(f"Error installing {package_name} using pip API: {e}", 'error')
        return False


def _find_wheel_for_package(package_name, libs_path):
    """
    Find if there's a .whl file for the given package in libs_path.
    
    :param package_name: Name of the package to find
    :param libs_path: Path to the libs directory
    :return: Full path to .whl file if found, None otherwise
    """
    if not os.path.exists(libs_path):
        _log(f"Libs path does not exist: {libs_path}", 'warning')
        return None
    
    try:
        whl_files = [f for f in os.listdir(libs_path) if f.endswith('.whl')]
        _log(f"Found {len(whl_files)} .whl files in libs: {', '.join(whl_files)}", 'debug')
    except Exception as e:
        _log(f"Error reading libs directory: {e}", 'error')
        return None
    
    # Normalize package name: replace underscores with hyphens
    package_name_normalized = package_name.lower().replace('_', '-')
    
    for file in whl_files:
        # Extract package name from wheel filename
        # Format: package_name-version-py_version-abi-platform.whl
        whl_package_name = file.split('-')[0].lower().replace('_', '-')
        
        if whl_package_name == package_name_normalized:
            _log(f"Found wheel file for '{package_name}': {file}", 'info')
            return os.path.join(libs_path, file)
    
    _log(f"No wheel file found for '{package_name}'", 'warning')
    return None


def check(required_packages):
    """
    Check if required packages are installed and prompt to install them if missing.
    Priority: installed -> local .whl files -> internet download

    :param required_packages: List of required package names.
    """
    _log("Starting dependency check...", 'info')
    _log(f"Required packages: {', '.join(required_packages)}", 'info')
    
    # Get path to plugin root: check_dependencies.py -> install_packages -> DXF-PostGIS-Converter
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    libs_path = os.path.join(plugin_root, 'libs')
    _log(f"Plugin root: {plugin_root}", 'debug')
    _log(f"Libs path: {libs_path}", 'debug')
    
    # Step 1: Check what's already installed
    missing_packages = []
    for package in required_packages:
        try:
            importlib.import_module(package)
        except:
            missing_packages.append(package)
    
    if not missing_packages:
        _log("All packages are installed. Done!", 'info')
        return  # All packages are installed
    
    _log(f"Missing packages ({len(missing_packages)}): {', '.join(missing_packages)}", 'info')
    
    # Step 2: Check what's available in .whl files
    _log("Checking local .whl files...", 'info')
    packages_in_wheels = {}
    packages_need_internet = []
    
    for package in missing_packages:
        wheel_path = _find_wheel_for_package(package, libs_path)
        if wheel_path:
            packages_in_wheels[package] = wheel_path
        else:
            packages_need_internet.append(package)
    
    # Step 3: Install from local .whl files first
    if packages_in_wheels:
        for package, wheel_path in packages_in_wheels.items():
            try:
                if _install_package(package, libs_path):
                    _log(f"{package} installed successfully from .whl", 'info')
                else:
                    _log(f"Failed to install {package} from .whl", 'error')
                    packages_need_internet.append(package)
            except Exception as e:
                _log(f"Exception installing {package} from .whl: {e}", 'error')
                packages_need_internet.append(package)
    
    # Clear cache after local installations
    importlib.invalidate_caches()
    
    # Step 4: Ask user about remaining packages that need internet
    if packages_need_internet:
        _log(f"{len(packages_need_internet)} packages need internet download: {', '.join(packages_need_internet)}", 'warning')
        
        message = "The following Python packages are required but not found locally:\n\n"
        message += "\n".join(packages_need_internet)
        message += "\n\nWould you like to download and install them from the internet? After installation please restart QGIS."

        reply = QMessageBox.question(None, 'Missing Dependencies', message,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.No:
            _log("User declined to download packages from internet", 'warning')
            return

        for package in packages_need_internet:
            try:
                _log(f"Downloading and installing {package}...", 'info')
                if _install_package(package):
                    _log(f"{package} installed successfully from internet", 'info')
                else:
                    _log(f"Failed to install {package} from internet", 'error')
            except Exception as e:
                _log(f"Exception installing {package}: {e}", 'error')
    
    _log("Dependency check completed!", 'info')
