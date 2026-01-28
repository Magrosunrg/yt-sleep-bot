import 'dart:async';
import 'package:flutter/foundation.dart';
import '../models/exploration_state.dart';
import '../models/exploration_event.dart';
import 'storage_service.dart';
import 'event_generator.dart';
import 'lunar_game_service.dart';

class ExplorationService extends ChangeNotifier {
  final StorageService _storageService;
  final LunarGameService _lunarGameService;
  final EventGenerator _eventGenerator = EventGenerator();
  
  ExplorationState _state = ExplorationState.initial();
  Timer? _explorationTimer;
  
  static const String _storageKey = 'exploration_state';
  static const int _eventIntervalMinSeconds = 3;
  static const int _eventIntervalMaxSeconds = 8;
  static const int _difficultyIncreaseIntervalSeconds = 120;

  ExplorationService(this._storageService, this._lunarGameService) {
    _loadState();
  }

  ExplorationState get state => _state;
  bool get isExploring => _state.isExploring;
  int get difficultyLevel => _state.difficultyLevel;
  List<ExplorationEvent> get eventHistory => _state.eventHistory;
  int get totalMoonlightEarned => _state.totalMoonlightEarned;
  
  int get currentExplorationTimeSeconds {
    if (!_state.isExploring) {
      return _state.totalExplorationTime ~/ 1000;
    }
    final now = DateTime.now().millisecondsSinceEpoch;
    final current = (now - _state.explorationStartTime) ~/ 1000;
    return (_state.totalExplorationTime ~/ 1000) + current;
  }

  Future<void> _loadState() async {
    final stored = _storageService.loadJson(_storageKey);
    if (stored != null) {
      try {
        _state = ExplorationState.fromJson(stored);
        if (_state.isExploring) {
          _startExplorationTimer();
        }
      } catch (e) {
        debugPrint('Error loading exploration state: $e');
        _state = ExplorationState.initial();
      }
    }
  }

  Future<void> _saveState() async {
    await _storageService.saveJson(_storageKey, _state.toJson());
  }

  void startExploration() {
    if (_state.isExploring) return;

    final now = DateTime.now().millisecondsSinceEpoch;
    _state = _state.copyWith(
      isExploring: true,
      explorationStartTime: now,
    );

    _startExplorationTimer();
    _saveState();
    notifyListeners();
  }

  void stopExploration() {
    if (!_state.isExploring) return;

    final now = DateTime.now().millisecondsSinceEpoch;
    final sessionTime = now - _state.explorationStartTime;
    
    _state = _state.copyWith(
      isExploring: false,
      totalExplorationTime: _state.totalExplorationTime + sessionTime,
      explorationStartTime: 0,
    );

    _stopExplorationTimer();
    _saveState();
    notifyListeners();
  }

  void _startExplorationTimer() {
    _stopExplorationTimer();
    _scheduleNextEvent();
  }

  void _stopExplorationTimer() {
    _explorationTimer?.cancel();
    _explorationTimer = null;
  }

  void _scheduleNextEvent() {
    if (!_state.isExploring) return;

    final delaySeconds = _eventIntervalMinSeconds + 
        ((_eventIntervalMaxSeconds - _eventIntervalMinSeconds) * 
        (1.0 - (currentExplorationTimeSeconds / 300.0).clamp(0.0, 1.0)));

    _explorationTimer = Timer(
      Duration(seconds: delaySeconds.round()),
      _generateAndProcessEvent,
    );
  }

  void _generateAndProcessEvent() {
    if (!_state.isExploring) return;

    final totalTimeSeconds = currentExplorationTimeSeconds;
    final newDifficultyLevel = 1 + (totalTimeSeconds ~/ _difficultyIncreaseIntervalSeconds);
    
    final event = _eventGenerator.generateEvent(totalTimeSeconds, newDifficultyLevel);
    
    _addEvent(event);
    _awardMoonlight(event.moonlightReward);
    
    _state = _state.copyWith(difficultyLevel: newDifficultyLevel);
    
    _scheduleNextEvent();
  }

  void _addEvent(ExplorationEvent event) {
    final updatedHistory = List<ExplorationEvent>.from(_state.eventHistory);
    updatedHistory.add(event);
    
    if (updatedHistory.length > 100) {
      updatedHistory.removeAt(0);
    }
    
    _state = _state.copyWith(eventHistory: updatedHistory);
    _saveState();
    notifyListeners();
  }

  void _awardMoonlight(int amount) {
    _lunarGameService.addMoonlight(amount);
    _state = _state.copyWith(
      totalMoonlightEarned: _state.totalMoonlightEarned + amount,
    );
    _saveState();
  }

  void clearHistory() {
    _state = _state.copyWith(eventHistory: []);
    _saveState();
    notifyListeners();
  }

  Future<void> resetExploration() async {
    _stopExplorationTimer();
    _state = ExplorationState.initial();
    await _saveState();
    notifyListeners();
  }

  void onAppPaused() {
    if (_state.isExploring) {
      final now = DateTime.now().millisecondsSinceEpoch;
      final sessionTime = now - _state.explorationStartTime;
      _state = _state.copyWith(
        totalExplorationTime: _state.totalExplorationTime + sessionTime,
        explorationStartTime: now,
      );
      _saveState();
    }
    _stopExplorationTimer();
  }

  void onAppResumed() {
    if (_state.isExploring) {
      final now = DateTime.now().millisecondsSinceEpoch;
      _state = _state.copyWith(explorationStartTime: now);
      _startExplorationTimer();
    }
  }

  @override
  void dispose() {
    _stopExplorationTimer();
    super.dispose();
  }
}
