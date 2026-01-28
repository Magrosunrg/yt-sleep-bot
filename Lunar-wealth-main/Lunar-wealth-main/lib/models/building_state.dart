import 'building_room.dart';

class BuildingState {
  final String id;
  final String buildingName;
  final BuildingRoom currentRoom;
  final List<BuildingRoom> completedRooms;
  final Map<String, int> collectedLoot;
  final Map<String, dynamic> temporaryModifiers;
  final int currentDifficultyLevel;
  final bool isCompleted;
  final bool isCombatTriggered;

  const BuildingState({
    required this.id,
    required this.buildingName,
    required this.currentRoom,
    this.completedRooms = const [],
    this.collectedLoot = const {},
    this.temporaryModifiers = const {},
    this.currentDifficultyLevel = 1,
    this.isCompleted = false,
    this.isCombatTriggered = false,
  });

  int get roomCount => completedRooms.length;
  int get totalLoot => collectedLoot.values.fold(0, (sum, val) => sum + val);

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'buildingName': buildingName,
      'currentRoom': currentRoom.toJson(),
      'completedRooms': completedRooms.map((r) => r.toJson()).toList(),
      'collectedLoot': collectedLoot,
      'temporaryModifiers': temporaryModifiers,
      'currentDifficultyLevel': currentDifficultyLevel,
      'isCompleted': isCompleted,
      'isCombatTriggered': isCombatTriggered,
    };
  }

  factory BuildingState.fromJson(Map<String, dynamic> json) {
    return BuildingState(
      id: json['id'] as String,
      buildingName: json['buildingName'] as String,
      currentRoom:
          BuildingRoom.fromJson(json['currentRoom'] as Map<String, dynamic>),
      completedRooms: (json['completedRooms'] as List<dynamic>?)
              ?.map((r) => BuildingRoom.fromJson(r as Map<String, dynamic>))
              .toList() ??
          [],
      collectedLoot:
          Map<String, int>.from(json['collectedLoot'] as Map? ?? {}),
      temporaryModifiers:
          json['temporaryModifiers'] as Map<String, dynamic>? ?? {},
      currentDifficultyLevel: json['currentDifficultyLevel'] as int? ?? 1,
      isCompleted: json['isCompleted'] as bool? ?? false,
      isCombatTriggered: json['isCombatTriggered'] as bool? ?? false,
    );
  }

  BuildingState copyWith({
    String? id,
    String? buildingName,
    BuildingRoom? currentRoom,
    List<BuildingRoom>? completedRooms,
    Map<String, int>? collectedLoot,
    Map<String, dynamic>? temporaryModifiers,
    int? currentDifficultyLevel,
    bool? isCompleted,
    bool? isCombatTriggered,
  }) {
    return BuildingState(
      id: id ?? this.id,
      buildingName: buildingName ?? this.buildingName,
      currentRoom: currentRoom ?? this.currentRoom,
      completedRooms: completedRooms ?? this.completedRooms,
      collectedLoot: collectedLoot ?? this.collectedLoot,
      temporaryModifiers: temporaryModifiers ?? this.temporaryModifiers,
      currentDifficultyLevel:
          currentDifficultyLevel ?? this.currentDifficultyLevel,
      isCompleted: isCompleted ?? this.isCompleted,
      isCombatTriggered: isCombatTriggered ?? this.isCombatTriggered,
    );
  }
}
