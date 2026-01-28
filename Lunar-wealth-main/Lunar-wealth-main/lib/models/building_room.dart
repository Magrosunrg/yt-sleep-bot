import 'choice_option.dart';

enum RoomType {
  entrance,
  hazard,
  loot,
  npc,
  treasure,
  encounter,
  boss,
}

enum HazardType {
  spike,
  fire,
  ice,
  poison,
  electricity,
  none,
}

class BuildingRoom {
  final String id;
  final String title;
  final String description;
  final RoomType type;
  final HazardType hazardType;
  final List<ChoiceOption> choices;
  final Map<String, int> rewards;
  final Map<String, dynamic> eventData;

  const BuildingRoom({
    required this.id,
    required this.title,
    required this.description,
    required this.type,
    this.hazardType = HazardType.none,
    required this.choices,
    this.rewards = const {},
    this.eventData = const {},
  });

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'description': description,
      'type': type.index,
      'hazardType': hazardType.index,
      'choices': choices.map((c) => c.toJson()).toList(),
      'rewards': rewards,
      'eventData': eventData,
    };
  }

  factory BuildingRoom.fromJson(Map<String, dynamic> json) {
    return BuildingRoom(
      id: json['id'] as String,
      title: json['title'] as String,
      description: json['description'] as String,
      type: RoomType.values[json['type'] as int],
      hazardType: HazardType.values[json['hazardType'] as int? ?? 5],
      choices: (json['choices'] as List<dynamic>?)
              ?.map((c) => ChoiceOption.fromJson(c as Map<String, dynamic>))
              .toList() ??
          [],
      rewards: Map<String, int>.from(json['rewards'] as Map? ?? {}),
      eventData: json['eventData'] as Map<String, dynamic>? ?? {},
    );
  }

  BuildingRoom copyWith({
    String? id,
    String? title,
    String? description,
    RoomType? type,
    HazardType? hazardType,
    List<ChoiceOption>? choices,
    Map<String, int>? rewards,
    Map<String, dynamic>? eventData,
  }) {
    return BuildingRoom(
      id: id ?? this.id,
      title: title ?? this.title,
      description: description ?? this.description,
      type: type ?? this.type,
      hazardType: hazardType ?? this.hazardType,
      choices: choices ?? this.choices,
      rewards: rewards ?? this.rewards,
      eventData: eventData ?? this.eventData,
    );
  }
}
