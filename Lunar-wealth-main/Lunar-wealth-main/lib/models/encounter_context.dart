class EncounterContext {
  final String id;
  final int difficultyLevel;
  final int minEnemies;
  final int maxEnemies;
  final Map<String, int> resourceScaling;
  final bool isSoloEncounter;
  final int elapsedTimeSeconds;

  const EncounterContext({
    required this.id,
    required this.difficultyLevel,
    required this.minEnemies,
    required this.maxEnemies,
    required this.resourceScaling,
    required this.isSoloEncounter,
    required this.elapsedTimeSeconds,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'difficultyLevel': difficultyLevel,
      'minEnemies': minEnemies,
      'maxEnemies': maxEnemies,
      'resourceScaling': resourceScaling,
      'isSoloEncounter': isSoloEncounter,
      'elapsedTimeSeconds': elapsedTimeSeconds,
    };
  }

  factory EncounterContext.fromJson(Map<String, dynamic> json) {
    return EncounterContext(
      id: json['id'] as String,
      difficultyLevel: json['difficultyLevel'] as int,
      minEnemies: json['minEnemies'] as int,
      maxEnemies: json['maxEnemies'] as int,
      resourceScaling: Map<String, int>.from(json['resourceScaling'] as Map),
      isSoloEncounter: json['isSoloEncounter'] as bool,
      elapsedTimeSeconds: json['elapsedTimeSeconds'] as int,
    );
  }

  EncounterContext copyWith({
    String? id,
    int? difficultyLevel,
    int? minEnemies,
    int? maxEnemies,
    Map<String, int>? resourceScaling,
    bool? isSoloEncounter,
    int? elapsedTimeSeconds,
  }) {
    return EncounterContext(
      id: id ?? this.id,
      difficultyLevel: difficultyLevel ?? this.difficultyLevel,
      minEnemies: minEnemies ?? this.minEnemies,
      maxEnemies: maxEnemies ?? this.maxEnemies,
      resourceScaling: resourceScaling ?? this.resourceScaling,
      isSoloEncounter: isSoloEncounter ?? this.isSoloEncounter,
      elapsedTimeSeconds: elapsedTimeSeconds ?? this.elapsedTimeSeconds,
    );
  }
}
