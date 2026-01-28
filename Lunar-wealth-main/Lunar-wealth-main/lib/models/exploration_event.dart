enum EventType {
  buildingDiscovery,
  encounter,
  treasure,
  challenge,
  peaceful,
}

class ExplorationEvent {
  final String id;
  final EventType type;
  final String title;
  final String description;
  final int moonlightReward;
  final DateTime timestamp;
  final int difficultyLevel;

  const ExplorationEvent({
    required this.id,
    required this.type,
    required this.title,
    required this.description,
    required this.moonlightReward,
    required this.timestamp,
    required this.difficultyLevel,
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'type': type.index,
      'title': title,
      'description': description,
      'moonlightReward': moonlightReward,
      'timestamp': timestamp.toIso8601String(),
      'difficultyLevel': difficultyLevel,
    };
  }

  factory ExplorationEvent.fromJson(Map<String, dynamic> json) {
    return ExplorationEvent(
      id: json['id'] as String,
      type: EventType.values[json['type'] as int],
      title: json['title'] as String,
      description: json['description'] as String,
      moonlightReward: json['moonlightReward'] as int,
      timestamp: DateTime.parse(json['timestamp'] as String),
      difficultyLevel: json['difficultyLevel'] as int,
    );
  }

  ExplorationEvent copyWith({
    String? id,
    EventType? type,
    String? title,
    String? description,
    int? moonlightReward,
    DateTime? timestamp,
    int? difficultyLevel,
  }) {
    return ExplorationEvent(
      id: id ?? this.id,
      type: type ?? this.type,
      title: title ?? this.title,
      description: description ?? this.description,
      moonlightReward: moonlightReward ?? this.moonlightReward,
      timestamp: timestamp ?? this.timestamp,
      difficultyLevel: difficultyLevel ?? this.difficultyLevel,
    );
  }
}
