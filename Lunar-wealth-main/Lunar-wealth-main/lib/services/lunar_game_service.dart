import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/player_state.dart';
import 'storage_service.dart';

class LunarGameService extends ChangeNotifier {
  final StorageService _storageService;
  late PlayerState _playerState;
  Timer? _healingTimer;
  
  Function(int)? onMoonlightGained;

  static const String _playerStateKey = 'player_state';
  static const int _healingTickInterval = 500;
  static const double _healingPercentPerSecond = 0.015;

  LunarGameService(this._storageService) {
    _loadState();
    _startHealingIfNeeded();
  }

  PlayerState get playerState => _playerState;
  bool get isHealing => _healingTimer != null && _healingTimer!.isActive;
  
  // Getters for UI convenience
  int get moonlight => _playerState.moonlight;
  int get streakCount => 0; // Placeholder until streak mechanic is implemented

  void _loadState() {
    final savedData = _storageService.loadJson(_playerStateKey);
    if (savedData != null) {
      _playerState = PlayerState.fromJson(savedData);
    } else {
      _playerState = PlayerState.initial();
    }
  }

  Future<void> saveState() async {
    await _storageService.saveJson(_playerStateKey, _playerState.toJson());
  }

  void updatePlayerName(String name) {
    _playerState = _playerState.copyWith(playerName: name);
    saveState();
    notifyListeners();
  }

  void updateHp(int hp) {
    _playerState = _playerState.copyWith(hp: hp);
    saveState();
    notifyListeners();
    _startHealingIfNeeded();
  }

  void updateMoonlight(int moonlight) {
    _playerState = _playerState.copyWith(moonlight: moonlight);
    saveState();
    notifyListeners();
  }

  void addMoonlight(int amount) {
    final newAmount = _playerState.moonlight + amount;
    updateMoonlight(newAmount);
    if (onMoonlightGained != null && amount > 0) {
      onMoonlightGained!(amount);
    }
  }

  void consumeMoonlight(int amount) {
    final newAmount = (_playerState.moonlight - amount).clamp(0, 999999);
    updateMoonlight(newAmount);
  }

  bool hasMoonlight(int amount) {
    return _playerState.moonlight >= amount;
  }

  void addResource(String resourceType, int amount) {
    final newResources = Map<String, int>.from(_playerState.resources);
    newResources[resourceType] = (newResources[resourceType] ?? 0) + amount;
    _playerState = _playerState.copyWith(resources: newResources);
    saveState();
    notifyListeners();
  }

  void consumeResource(String resourceType, int amount) {
    final newResources = Map<String, int>.from(_playerState.resources);
    final current = newResources[resourceType] ?? 0;
    final remaining = (current - amount).clamp(0, 999999);
    if (remaining <= 0) {
      newResources.remove(resourceType);
    } else {
      newResources[resourceType] = remaining;
    }
    _playerState = _playerState.copyWith(resources: newResources);
    saveState();
    notifyListeners();
  }

  bool hasResource(String resourceType, int amount) {
    return (_playerState.resources[resourceType] ?? 0) >= amount;
  }

  int getResourceAmount(String resourceType) {
    return _playerState.resources[resourceType] ?? 0;
  }

  Map<String, int> getAllResources() {
    return Map<String, int>.from(_playerState.resources);
  }

  void setBuildRunFlag(bool inBuildRun) {
    _playerState = _playerState.copyWith(isInBuildRun: inBuildRun);
    saveState();
    notifyListeners();
  }

  bool get isInBuildRun => _playerState.isInBuildRun;

  void updatePlayerState(PlayerState newState) {
    _playerState = newState;
    saveState();
    notifyListeners();
    _startHealingIfNeeded();
  }

  void unlockLocation(String location) {
    if (!_playerState.unlockedLocations.contains(location)) {
      final newLocations = List<String>.from(_playerState.unlockedLocations);
      newLocations.add(location);
      _playerState = _playerState.copyWith(unlockedLocations: newLocations);
      saveState();
      notifyListeners();
    }
  }

  void resetGame() {
    _playerState = PlayerState.initial();
    saveState();
    notifyListeners();
  }

  void _startHealingIfNeeded() {
    if (_playerState.hp >= _playerState.maxHp) {
      _stopHealing();
      return;
    }

    _healingTimer?.cancel();
    _healingTimer = Timer.periodic(
      const Duration(milliseconds: _healingTickInterval),
      (_) => _healTick(),
    );
  }

  void _stopHealing() {
    _healingTimer?.cancel();
    _healingTimer = null;
  }

  void _healTick() {
    if (_playerState.hp >= _playerState.maxHp) {
      _stopHealing();
      return;
    }

    final healAmount = (_playerState.maxHp * _healingPercentPerSecond * (_healingTickInterval / 1000.0)).ceil();
    final newHp = (_playerState.hp + healAmount).clamp(0, _playerState.maxHp);
    
    if (newHp != _playerState.hp) {
      updateHp(newHp);
    }

    if (newHp >= _playerState.maxHp) {
      _stopHealing();
    }
  }

  void onAppPaused() {
    _stopHealing();
    saveState();
  }

  void onAppResumed() {
    _startHealingIfNeeded();
  }

  @override
  void dispose() {
    _stopHealing();
    super.dispose();
  }
}
