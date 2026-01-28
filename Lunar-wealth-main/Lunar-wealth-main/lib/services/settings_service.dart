import 'package:flutter/foundation.dart';
import 'storage_service.dart';

class SettingsService extends ChangeNotifier {
  final StorageService _storageService;

  static const String _settingsKey = 'app_settings';

  bool _masterVolumeEnabled = true;
  bool _soundEffectsEnabled = true;
  bool _musicEnabled = true;
  String _gameSpeed = 'normal';
  String _difficulty = 'normal';
  bool _autoPauseOnChoice = true;
  String _textSize = 'normal';

  SettingsService(this._storageService) {
    _loadSettings();
  }

  bool get masterVolumeEnabled => _masterVolumeEnabled;
  bool get soundEffectsEnabled => _soundEffectsEnabled;
  bool get musicEnabled => _musicEnabled;
  String get gameSpeed => _gameSpeed;
  String get difficulty => _difficulty;
  bool get autoPauseOnChoice => _autoPauseOnChoice;
  String get textSize => _textSize;

  int get minEventIntervalSeconds {
    switch (_gameSpeed) {
      case 'slow':
        return 5;
      case 'fast':
        return 1;
      case 'normal':
      default:
        return 3;
    }
  }

  int get maxEventIntervalSeconds {
    switch (_gameSpeed) {
      case 'slow':
        return 12;
      case 'fast':
        return 3;
      case 'normal':
      default:
        return 8;
    }
  }

  double get textSizeMultiplier {
    switch (_textSize) {
      case 'small':
        return 0.85;
      case 'large':
        return 1.15;
      case 'normal':
      default:
        return 1.0;
    }
  }

  void _loadSettings() {
    final data = _storageService.loadJson(_settingsKey);
    if (data != null) {
      _masterVolumeEnabled = data['masterVolumeEnabled'] as bool? ?? true;
      _soundEffectsEnabled = data['soundEffectsEnabled'] as bool? ?? true;
      _musicEnabled = data['musicEnabled'] as bool? ?? true;
      _gameSpeed = data['gameSpeed'] as String? ?? 'normal';
      _difficulty = data['difficulty'] as String? ?? 'normal';
      _autoPauseOnChoice = data['autoPauseOnChoice'] as bool? ?? true;
      _textSize = data['textSize'] as String? ?? 'normal';
    }
  }

  Future<void> _saveSettings() async {
    await _storageService.saveJson(_settingsKey, {
      'masterVolumeEnabled': _masterVolumeEnabled,
      'soundEffectsEnabled': _soundEffectsEnabled,
      'musicEnabled': _musicEnabled,
      'gameSpeed': _gameSpeed,
      'difficulty': _difficulty,
      'autoPauseOnChoice': _autoPauseOnChoice,
      'textSize': _textSize,
    });
  }

  Future<void> setMasterVolume(bool enabled) async {
    _masterVolumeEnabled = enabled;
    await _saveSettings();
    notifyListeners();
  }

  Future<void> setSoundEffects(bool enabled) async {
    _soundEffectsEnabled = enabled;
    await _saveSettings();
    notifyListeners();
  }

  Future<void> setMusic(bool enabled) async {
    _musicEnabled = enabled;
    await _saveSettings();
    notifyListeners();
  }

  Future<void> setGameSpeed(String speed) async {
    if (['slow', 'normal', 'fast'].contains(speed)) {
      _gameSpeed = speed;
      await _saveSettings();
      notifyListeners();
    }
  }

  Future<void> setDifficulty(String difficulty) async {
    if (['easy', 'normal', 'hard'].contains(difficulty)) {
      _difficulty = difficulty;
      await _saveSettings();
      notifyListeners();
    }
  }

  Future<void> setAutoPauseOnChoice(bool enabled) async {
    _autoPauseOnChoice = enabled;
    await _saveSettings();
    notifyListeners();
  }

  Future<void> setTextSize(String size) async {
    if (['small', 'normal', 'large'].contains(size)) {
      _textSize = size;
      await _saveSettings();
      notifyListeners();
    }
  }

  Future<void> resetToDefaults() async {
    _masterVolumeEnabled = true;
    _soundEffectsEnabled = true;
    _musicEnabled = true;
    _gameSpeed = 'normal';
    _difficulty = 'normal';
    _autoPauseOnChoice = true;
    _textSize = 'normal';
    await _saveSettings();
    notifyListeners();
  }
}
