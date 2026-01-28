import 'exploration_event.dart';

class ExplorationState {
  final bool isExploring;
  final int explorationStartTime;
  final int totalExplorationTime;
  final List<ExplorationEvent> eventHistory;
  final int difficultyLevel;
  final int totalMoonlightEarned;

  const ExplorationState({
    required this.isExploring,
    required this.explorationStartTime,
    required this.totalExplorationTime,
    required this.eventHistory,
    required this.difficultyLevel,
    required this.totalMoonlightEarned,
  });

  factory ExplorationState.initial() {
    return const ExplorationState(
      isExploring: false,
      explorationStartTime: 0,
      totalExplorationTime: 0,
      eventHistory: [],
      difficultyLevel: 1,
      totalMoonlightEarned: 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'isExploring': isExploring,
      'explorationStartTime': explorationStartTime,
      'totalExplorationTime': totalExplorationTime,
      'eventHistory': eventHistory.map((e) => e.toJson()).toList(),
      'difficultyLevel': difficultyLevel,
      'totalMoonlightEarned': totalMoonlightEarned,
    };
  }

  factory ExplorationState.fromJson(Map<String, dynamic> json) {
    return ExplorationState(
      isExploring: json['isExploring'] as bool? ?? false,
      explorationStartTime: json['explorationStartTime'] as int? ?? 0,
      totalExplorationTime: json['totalExplorationTime'] as int? ?? 0,
      eventHistory: (json['eventHistory'] as List<dynamic>?)
              ?.map((e) => ExplorationEvent.fromJson(e as Map<String, dynamic>))
              .toList() ??
          const [],
      difficultyLevel: json['difficultyLevel'] as int? ?? 1,
      totalMoonlightEarned: json['totalMoonlightEarned'] as int? ?? 0,
    );
  }

  ExplorationState copyWith({
    bool? isExploring,
    int? explorationStartTime,
    int? totalExplorationTime,
    List<ExplorationEvent>? eventHistory,
    int? difficultyLevel,
    int? totalMoonlightEarned,
  }) {
    return ExplorationState(
      isExploring: isExploring ?? this.isExploring,
      explorationStartTime: explorationStartTime ?? this.explorationStartTime,
      totalExplorationTime: totalExplorationTime ?? this.totalExplorationTime,
      eventHistory: eventHistory ?? this.eventHistory,
      difficultyLevel: difficultyLevel ?? this.difficultyLevel,
      totalMoonlightEarned: totalMoonlightEarned ?? this.totalMoonlightEarned,
    );
  }

  int get currentExplorationDuration {
    if (!isExploring) return 0;
    final now = DateTime.now().millisecondsSinceEpoch;
    return now - explorationStartTime;
  }
}
