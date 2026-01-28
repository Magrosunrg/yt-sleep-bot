import 'choice_option.dart';
import 'encounter_context.dart';

enum LogEntryType {
  exploration,
  encounter,
  discovery,
  reward,
  challenge,
}

enum LogLevel {
  info,
  encounter,
  warning,
  loot,
  combat,
  event,
  damage,
}

LogLevel logLevelForEntryType(LogEntryType type) {
  switch (type) {
    case LogEntryType.exploration:
      return LogLevel.info;
    case LogEntryType.encounter:
      return LogLevel.encounter;
    case LogEntryType.discovery:
      return LogLevel.event;
    case LogEntryType.reward:
      return LogLevel.loot;
    case LogEntryType.challenge:
      return LogLevel.warning;
  }
}

LogLevel _parseLogLevel(dynamic storedValue, LogEntryType fallbackType) {
  if (storedValue is String) {
    final normalizedValue = storedValue.toLowerCase();
    for (final level in LogLevel.values) {
      if (level.name == normalizedValue) {
        return level;
      }
    }
  } else if (storedValue is int) {
    if (storedValue >= 0 && storedValue < LogLevel.values.length) {
      return LogLevel.values[storedValue];
    }
  }

  return logLevelForEntryType(fallbackType);
}

extension LogLevelLabel on LogLevel {
  String get label => name.toUpperCase();
}

class ExplorationLogEntry {
  final String id;
  final LogEntryType type;
  final LogLevel logLevel;
  final String title;
  final String description;
  final DateTime timestamp;
  final int difficultyLevel;
  final int elapsedTimeSeconds;
  final Map<String, int> rewards;
  final List<ChoiceOption> choices;
  final EncounterContext? encounterContext;
  final bool isResolved;
  final String? chosenOptionId;
  final Map<String, dynamic> eventData;

  const ExplorationLogEntry({
    required this.id,
    required this.type,
    required this.logLevel,
    required this.title,
    required this.description,
    required this.timestamp,
    required this.difficultyLevel,
    required this.elapsedTimeSeconds,
    required this.rewards,
    required this.choices,
    this.encounterContext,
    this.isResolved = false,
    this.chosenOptionId,
    this.eventData = const {},
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type.index,
      'logLevel': logLevel.name,
      'title': title,
      'description': description,
      'timestamp': timestamp.toIso8601String(),
      'difficultyLevel': difficultyLevel,
      'elapsedTimeSeconds': elapsedTimeSeconds,
      'rewards': rewards,
      'choices': choices.map((c) => c.toJson()).toList(),
      'encounterContext': encounterContext?.toJson(),
      'isResolved': isResolved,
      'chosenOptionId': chosenOptionId,
      'eventData': eventData,
    };
  }

  factory ExplorationLogEntry.fromJson(Map<String, dynamic> json) {
    final type = LogEntryType.values[json['type'] as int];
    final storedLogLevel = json['logLevel'];

    return ExplorationLogEntry(
      id: json['id'] as String,
      type: type,
      logLevel: _parseLogLevel(storedLogLevel, type),
      title: json['title'] as String,
      description: json['description'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      difficultyLevel: json['difficultyLevel'] as int,
      elapsedTimeSeconds: json['elapsedTimeSeconds'] as int,
      rewards: Map<String, int>.from(json['rewards'] as Map),
      choices: (json['choices'] as List<dynamic>?)
              ?.map((c) => ChoiceOption.fromJson(c as Map<String, dynamic>))
              .toList() ??
          [],
      encounterContext: json['encounterContext'] != null
          ? EncounterContext.fromJson(
              json['encounterContext'] as Map<String, dynamic>)
          : null,
      isResolved: json['isResolved'] as bool? ?? false,
      chosenOptionId: json['chosenOptionId'] as String?,
      eventData: json['eventData'] as Map<String, dynamic>? ?? {},
    );
  }

  ExplorationLogEntry copyWith({
    String? id,
    LogEntryType? type,
    LogLevel? logLevel,
    String? title,
    String? description,
    DateTime? timestamp,
    int? difficultyLevel,
    int? elapsedTimeSeconds,
    Map<String, int>? rewards,
    List<ChoiceOption>? choices,
    EncounterContext? encounterContext,
    bool? isResolved,
    String? chosenOptionId,
    Map<String, dynamic>? eventData,
  }) {
    return ExplorationLogEntry(
      id: id ?? this.id,
      type: type ?? this.type,
      logLevel: logLevel ?? this.logLevel,
      title: title ?? this.title,
      description: description ?? this.description,
      timestamp: timestamp ?? this.timestamp,
      difficultyLevel: difficultyLevel ?? this.difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds ?? this.elapsedTimeSeconds,
      rewards: rewards ?? this.rewards,
      choices: choices ?? this.choices,
      encounterContext: encounterContext ?? this.encounterContext,
      isResolved: isResolved ?? this.isResolved,
      chosenOptionId: chosenOptionId ?? this.chosenOptionId,
      eventData: eventData ?? this.eventData,
    );
  }
}
