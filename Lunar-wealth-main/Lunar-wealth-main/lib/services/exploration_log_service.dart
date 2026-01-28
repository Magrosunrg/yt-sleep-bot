import 'dart:async';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import '../models/log_entry.dart';
import '../models/encounter_context.dart';
import 'storage_service.dart';
import 'log_entry_generator.dart';
import 'lunar_game_service.dart';
import 'settings_service.dart';

class ExplorationLogService extends ChangeNotifier {
  final StorageService _storageService;
  final LunarGameService _gameService;
  final SettingsService? _settingsService;
  final LogEntryGenerator _generator = LogEntryGenerator();
  final Random _random = Random();
  final Connectivity _connectivity = Connectivity();

  late List<ExplorationLogEntry> _logHistory;
  late int _explorationStartTime;
  bool _isExploring = false;
  bool _isPaused = false;
  bool _isOnline = true;
  Timer? _logTimer;
  StreamSubscription<ConnectivityResult>? _connectivitySubscription;
  int _entriesSinceLastChoice = 0;
  int _nextChoiceThreshold = 0;

  static const String _logStorageKey = 'exploration_log_history';
  static const String _explorationStateKey = 'exploration_log_state';
  static const int _difficultyIncreaseIntervalSeconds = 120;
  static const int _minEntriesBetweenChoices = 5;
  static const int _maxEntriesBetweenChoices = 8;

  ExplorationLogService(
    this._storageService,
    this._gameService, {
    SettingsService? settingsService,
  }) : _settingsService = settingsService {
    _logHistory = [];
    _explorationStartTime = 0;
    _loadState();
    _initConnectivity();
  }

  int get _minEventIntervalSeconds =>
      _settingsService?.minEventIntervalSeconds ?? 3;
  int get _maxEventIntervalSeconds =>
      _settingsService?.maxEventIntervalSeconds ?? 8;

  List<ExplorationLogEntry> get logHistory => _logHistory;
  bool get isExploring => _isExploring;
  bool get isPaused => _isPaused;
  bool get isOnline => _isOnline;
  int get totalElapsedTimeSeconds {
    if (!_isExploring) return 0;
    final now = DateTime.now().millisecondsSinceEpoch;
    return ((now - _explorationStartTime) ~/ 1000).clamp(0, 999999);
  }

  int get currentDifficultyLevel {
    return 1 + (totalElapsedTimeSeconds ~/ _difficultyIncreaseIntervalSeconds);
  }

  int get totalMoonlightEarned {
    int total = 0;
    for (final entry in _logHistory) {
      if (entry.rewards.containsKey('moonlight')) {
        total += entry.rewards['moonlight']!;
      }
    }
    return total;
  }

  Future<void> _loadState() async {
    try {
      final historyJson = _storageService.loadJson(_logStorageKey);
      if (historyJson != null && historyJson['entries'] != null) {
        _logHistory = (historyJson['entries'] as List<dynamic>)
            .map((e) => ExplorationLogEntry.fromJson(e as Map<String, dynamic>))
            .toList();
      }

      final stateJson = _storageService.loadJson(_explorationStateKey);
      if (stateJson != null) {
        _isExploring = stateJson['isExploring'] as bool? ?? false;
        _explorationStartTime = stateJson['explorationStartTime'] as int? ?? 0;

        if (_isExploring) {
          _startLogTimer();
        }
      }
    } catch (e) {
      debugPrint('Error loading exploration log state: $e');
    }
  }

  Future<void> _saveState() async {
    try {
      await _storageService.saveJson(
        _logStorageKey,
        {'entries': _logHistory.map((e) => e.toJson()).toList()},
      );

      await _storageService.saveJson(
        _explorationStateKey,
        {
          'isExploring': _isExploring,
          'explorationStartTime': _explorationStartTime,
        },
      );
    } catch (e) {
      debugPrint('Error saving exploration log state: $e');
    }
  }

  Future<void> _initConnectivity() async {
    try {
      final result = await _connectivity.checkConnectivity();
      _isOnline = _isConnected(result);
      
      _connectivitySubscription = _connectivity.onConnectivityChanged.listen((result) {
        final wasOnline = _isOnline;
        _isOnline = _isConnected(result);
        
        if (wasOnline != _isOnline) {
          debugPrint('Connectivity changed: ${_isOnline ? "online" : "offline"}');
          notifyListeners();
        }
      });
    } catch (e) {
      debugPrint('Error initializing connectivity: $e');
      _isOnline = true;
    }
  }

  bool _isConnected(ConnectivityResult result) {
    return result == ConnectivityResult.mobile ||
        result == ConnectivityResult.wifi ||
        result == ConnectivityResult.ethernet;
  }

  void startExploration() {
    if (_isExploring) return;

    _isExploring = true;
    _explorationStartTime = DateTime.now().millisecondsSinceEpoch;
    _gameService.setBuildRunFlag(true);
    _entriesSinceLastChoice = 0;
    _nextChoiceThreshold = _random.nextInt(
      _maxEntriesBetweenChoices - _minEntriesBetweenChoices + 1,
    ) + _minEntriesBetweenChoices;

    _startLogTimer();
    _saveState();
    notifyListeners();
  }

  void stopExploration() {
    if (!_isExploring) return;

    _isExploring = false;
    _isPaused = false;
    _gameService.setBuildRunFlag(false);

    _stopLogTimer();
    _saveState();
    notifyListeners();
  }

  void pauseExploration() {
    if (!_isExploring || _isPaused) return;

    _isPaused = true;
    _stopLogTimer();
    _saveState();
    notifyListeners();
  }

  void resumeExploration() {
    if (!_isExploring || !_isPaused) return;

    _isPaused = false;
    _startLogTimer();
    _saveState();
    notifyListeners();
  }

  void _startLogTimer() {
    _stopLogTimer();
    _scheduleNextLogEntry();
  }

  void _stopLogTimer() {
    _logTimer?.cancel();
    _logTimer = null;
  }

  void _scheduleNextLogEntry() {
    if (!_isExploring || _isPaused) return;

    final delaySeconds = _minEventIntervalSeconds +
        ((_maxEventIntervalSeconds - _minEventIntervalSeconds) *
            (1.0 - (totalElapsedTimeSeconds / 300.0).clamp(0.0, 1.0)));

    _logTimer = Timer(
      Duration(seconds: delaySeconds.round()),
      _generateAndAddLogEntry,
    );
  }

  void _generateAndAddLogEntry() {
    if (!_isExploring) return;

    final allowChoices = _isOnline && _entriesSinceLastChoice >= _nextChoiceThreshold;

    final entry = _generator.generateLogEntry(
      totalElapsedTimeSeconds,
      currentDifficultyLevel,
      allowChoices: allowChoices,
    );

    if (allowChoices && entry.choices.isNotEmpty) {
      _entriesSinceLastChoice = 0;
      _nextChoiceThreshold = _random.nextInt(
        _maxEntriesBetweenChoices - _minEntriesBetweenChoices + 1,
      ) + _minEntriesBetweenChoices;
    } else {
      _entriesSinceLastChoice++;
    }

    _addLogEntry(entry);
    _applyLogEntryEffects(entry);

    if (entry.choices.isNotEmpty) {
      final autoPause = _settingsService?.autoPauseOnChoice ?? true;
      if (autoPause) {
        pauseExploration();
        return;
      }
    }

    _scheduleNextLogEntry();
  }

  void _addLogEntry(ExplorationLogEntry entry) {
    _logHistory.add(entry);

    if (_logHistory.length > 100) {
      _logHistory.removeAt(0);
    }

    _saveState();
    notifyListeners();
  }

  void _applyLogEntryEffects(ExplorationLogEntry entry) {
    if (entry.rewards.containsKey('moonlight')) {
      _gameService.addMoonlight(entry.rewards['moonlight']!);
    }

    for (final entry in entry.rewards.entries) {
      if (entry.key != 'moonlight') {
        _gameService.addResource(entry.key, entry.value);
      }
    }
  }

  void resolveLogEntry(String entryId, String chosenOptionId) {
    final entryIndex = _logHistory.indexWhere((e) => e.id == entryId);
    if (entryIndex < 0) return;

    final entry = _logHistory[entryIndex];
    final option = entry.choices.firstWhere(
      (o) => o.id == chosenOptionId,
      orElse: () => entry.choices.first,
    );

    _applyChoiceConsequences(option.consequences);

    final resolvedEntry =
        entry.copyWith(isResolved: true, chosenOptionId: chosenOptionId);
    _logHistory[entryIndex] = resolvedEntry;

    _saveState();
    notifyListeners();
  }

  void _applyChoiceConsequences(Map<String, dynamic> consequences) {
    for (final entry in consequences.entries) {
      if (entry.key == 'moonlight' && entry.value is int) {
        _gameService.addMoonlight(entry.value as int);
      } else if (entry.key == 'hp_restore' && entry.value is int) {
        final newHp = (_gameService.playerState.hp + (entry.value as int))
            .clamp(0, _gameService.playerState.maxHp);
        _gameService.updateHp(newHp);
      } else if (entry.key != 'requires_combat' && entry.value is int) {
        _gameService.addResource(entry.key, entry.value as int);
      }
    }

    _saveState();
  }

  void appendCombatResultEntry(
    String title,
    String description,
    Map<String, int> rewards,
    EncounterContext? context,
  ) {
    final timestamp = DateTime.now();
    final id =
        '${timestamp.millisecondsSinceEpoch}_combat_${_random.nextInt(1000)}';

    final entry = ExplorationLogEntry(
      id: id,
      type: LogEntryType.encounter,
      logLevel: LogLevel.combat,
      title: title,
      description: description,
      timestamp: timestamp,
      difficultyLevel: currentDifficultyLevel,
      elapsedTimeSeconds: totalElapsedTimeSeconds,
      rewards: rewards,
      choices: [],
      encounterContext: context,
      isResolved: true,
      chosenOptionId: 'combat_resolved',
    );

    _addLogEntry(entry);
  }

  void appendBuildingResultEntry(
    String title,
    String description,
    Map<String, int> rewards,
  ) {
    final timestamp = DateTime.now();
    final id =
        '${timestamp.millisecondsSinceEpoch}_building_${_random.nextInt(1000)}';

    final entry = ExplorationLogEntry(
      id: id,
      type: LogEntryType.discovery,
      logLevel: LogLevel.event,
      title: title,
      description: description,
      timestamp: timestamp,
      difficultyLevel: currentDifficultyLevel,
      elapsedTimeSeconds: totalElapsedTimeSeconds,
      rewards: rewards,
      choices: [],
      isResolved: true,
      chosenOptionId: 'building_completed',
    );

    _addLogEntry(entry);
    _applyLogEntryEffects(entry);
  }

  void clearHistory() {
    _logHistory.clear();
    _saveState();
    notifyListeners();
  }

  Future<void> resetExploration() async {
    stopExploration();
    _logHistory.clear();
    _explorationStartTime = 0;
    await _saveState();
    notifyListeners();
  }

  void onAppPaused() {
    if (_isExploring) {
      _stopLogTimer();
    }
  }

  void onAppResumed() {
    if (_isExploring) {
      _startLogTimer();
    }
  }

  @override
  void dispose() {
    _stopLogTimer();
    _connectivitySubscription?.cancel();
    super.dispose();
  }
}
