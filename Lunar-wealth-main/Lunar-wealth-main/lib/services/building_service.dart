// ignore_for_file: prefer_const_constructors
import 'package:flutter/foundation.dart';
import '../models/building_room.dart';
import '../models/building_state.dart';
import '../models/choice_option.dart';

class BuildingService extends ChangeNotifier {
  BuildingState? _currentBuilding;
  final Map<String, List<BuildingRoom>> _roomTemplates = {};

  BuildingService() {
    _initializeRoomTemplates();
  }

  BuildingState? get currentBuilding => _currentBuilding;
  bool get isInBuilding => _currentBuilding != null && !_currentBuilding!.isCompleted;

  void _initializeRoomTemplates() {
    _roomTemplates['tower'] = _generateTowerRooms();
    _roomTemplates['archive'] = _generateArchiveRooms();
    _roomTemplates['ruins'] = _generateRuinsRooms();
    _roomTemplates['shrine'] = _generateShrineRooms();
    _roomTemplates['vault'] = _generateVaultRooms();
  }

  List<BuildingRoom> _generateTowerRooms() {
    return [
      BuildingRoom(
        id: 'tower_1',
        title: 'Tower Entrance',
        description: 'You step into an ancient tower. Moonlight cascades down from above.',
        type: RoomType.entrance,
        choices: [
          ChoiceOption(
            id: 'ascend',
            label: 'Ascend the Stairs',
            description: 'Climb upward',
            consequences: {},
          ),
          ChoiceOption(
            id: 'turn_back',
            label: 'Turn Back',
            description: 'Leave the tower',
            consequences: {},
          ),
        ],
        rewards: {'moonlight': 5},
      ),
      BuildingRoom(
        id: 'tower_2',
        title: 'Crumbling Floor',
        description: 'The stone floor is unstable, with cracks revealing a chasm below.',
        type: RoomType.hazard,
        hazardType: HazardType.spike,
        choices: [
          ChoiceOption(
            id: 'careful_step',
            label: 'Step Carefully',
            description: 'Avoid the cracks',
            consequences: {'moonlight': 10},
          ),
          ChoiceOption(
            id: 'jump_across',
            label: 'Jump Across',
            description: 'Take the risk',
            consequences: {'moonlight': 20},
          ),
        ],
        rewards: {'moonlight': 15},
      ),
      BuildingRoom(
        id: 'tower_3',
        title: 'Guardian Chamber',
        description: 'A stone guardian sits motionless, watching the chamber.',
        type: RoomType.npc,
        choices: [
          ChoiceOption(
            id: 'speak',
            label: 'Speak to Guardian',
            description: 'Ask for knowledge',
            consequences: {'moonlight': 25, 'knowledge': 5},
          ),
          ChoiceOption(
            id: 'ignore',
            label: 'Ignore Guardian',
            description: 'Move past',
            consequences: {'moonlight': 5},
          ),
        ],
        rewards: {'moonlight': 25},
      ),
      BuildingRoom(
        id: 'tower_4',
        title: 'Tower Summit',
        description: 'At the peak, you find a chamber glowing with concentrated moonlight.',
        type: RoomType.treasure,
        choices: [
          ChoiceOption(
            id: 'claim',
            label: 'Claim the Moonlight',
            description: 'Take the treasure',
            consequences: {'moonlight': 50},
          ),
          ChoiceOption(
            id: 'meditate',
            label: 'Meditate Here',
            description: 'Absorb the power',
            consequences: {'moonlight': 75, 'hp_restore': 20},
          ),
        ],
        rewards: {'moonlight': 50},
      ),
    ];
  }

  List<BuildingRoom> _generateArchiveRooms() {
    return [
      BuildingRoom(
        id: 'archive_1',
        title: 'Archive Entrance',
        description: 'Dusty shelves stretch endlessly. Ancient texts glow faintly.',
        type: RoomType.entrance,
        choices: [
          ChoiceOption(
            id: 'search',
            label: 'Search the Shelves',
            description: 'Look for secrets',
            consequences: {},
          ),
          ChoiceOption(
            id: 'leave_archive',
            label: 'Leave Archive',
            description: 'Exit now',
            consequences: {},
          ),
        ],
        rewards: {'moonlight': 10},
      ),
      BuildingRoom(
        id: 'archive_2',
        title: 'Forbidden Section',
        description: 'Dangerous energy crackles around sealed books.',
        type: RoomType.hazard,
        hazardType: HazardType.electricity,
        choices: [
          ChoiceOption(
            id: 'read_carefully',
            label: 'Read Carefully',
            description: 'Avoid the energy',
            consequences: {'moonlight': 15},
          ),
          ChoiceOption(
            id: 'channel_power',
            label: 'Channel the Power',
            description: 'Embrace the energy',
            consequences: {'moonlight': 35, 'shadow_essence': 10},
          ),
        ],
        rewards: {'moonlight': 20},
      ),
      BuildingRoom(
        id: 'archive_3',
        title: 'Lunar Chronicle',
        description: 'A glowing manuscript reveals the history of the moon itself.',
        type: RoomType.loot,
        choices: [
          ChoiceOption(
            id: 'copy_knowledge',
            label: 'Copy Knowledge',
            description: 'Transcribe wisdom',
            consequences: {'moonlight': 30, 'knowledge': 10},
          ),
          ChoiceOption(
            id: 'skip_section',
            label: 'Skip This',
            description: 'Move on',
            consequences: {'moonlight': 5},
          ),
        ],
        rewards: {'moonlight': 30, 'knowledge': 5},
      ),
      BuildingRoom(
        id: 'archive_4',
        title: 'Inner Sanctum',
        description: 'The most ancient knowledge is stored here, pulsing with magic.',
        type: RoomType.treasure,
        choices: [
          ChoiceOption(
            id: 'learn_secrets',
            label: 'Learn Secrets',
            description: 'Gain wisdom',
            consequences: {'moonlight': 60, 'knowledge': 15},
          ),
          ChoiceOption(
            id: 'take_treasure',
            label: 'Take the Artifact',
            description: 'Grab an object',
            consequences: {'moonlight': 80},
          ),
        ],
        rewards: {'moonlight': 60},
      ),
    ];
  }

  List<BuildingRoom> _generateRuinsRooms() {
    return [
      BuildingRoom(
        id: 'ruins_1',
        title: 'Ruins Entrance',
        description: 'Crumbled stones mark the entrance to forgotten ruins.',
        type: RoomType.entrance,
        choices: [
          ChoiceOption(
            id: 'explore_ruins',
            label: 'Explore Deeper',
            description: 'Venture inside',
            consequences: {},
          ),
          ChoiceOption(
            id: 'leave_ruins',
            label: 'Leave Ruins',
            description: 'Turn away',
            consequences: {},
          ),
        ],
        rewards: {'moonlight': 8},
      ),
      BuildingRoom(
        id: 'ruins_2',
        title: 'Collapsed Passage',
        description: 'Rubble blocks the way, but passages branch to the sides.',
        type: RoomType.hazard,
        hazardType: HazardType.spike,
        choices: [
          ChoiceOption(
            id: 'left_path',
            label: 'Take Left Path',
            description: 'Risk instability',
            consequences: {'moonlight': 12},
          ),
          ChoiceOption(
            id: 'right_path',
            label: 'Take Right Path',
            description: 'Search for safety',
            consequences: {'moonlight': 18},
          ),
        ],
        rewards: {'moonlight': 15},
      ),
      BuildingRoom(
        id: 'ruins_3',
        title: 'Ancient Statue',
        description: 'A cracked statue holds an offering bowl filled with moonstone.',
        type: RoomType.loot,
        choices: [
          ChoiceOption(
            id: 'take_offering',
            label: 'Take Offering',
            description: 'Claim the stones',
            consequences: {'moonlight': 25, 'moonstone': 5},
          ),
          ChoiceOption(
            id: 'leave_offering',
            label: 'Leave Offering',
            description: 'Pay respects',
            consequences: {'moonlight': 8},
          ),
        ],
        rewards: {'moonlight': 25},
      ),
      BuildingRoom(
        id: 'ruins_4',
        title: 'Underground Lake',
        description: 'An underground lake reflects perfectly still moonlight.',
        type: RoomType.treasure,
        choices: [
          ChoiceOption(
            id: 'drink_water',
            label: 'Drink Sacred Water',
            description: 'Restore health',
            consequences: {'moonlight': 40, 'hp_restore': 30},
          ),
          ChoiceOption(
            id: 'collect_water',
            label: 'Collect Water',
            description: 'Gather essence',
            consequences: {'moonlight': 55, 'essence_vial': 3},
          ),
        ],
        rewards: {'moonlight': 45},
      ),
    ];
  }

  List<BuildingRoom> _generateShrineRooms() {
    return [
      BuildingRoom(
        id: 'shrine_1',
        title: 'Shrine Approach',
        description: 'Sacred moonstone pillars frame the shrine entrance.',
        type: RoomType.entrance,
        choices: [
          ChoiceOption(
            id: 'enter_shrine',
            label: 'Enter the Shrine',
            description: 'Step inside',
            consequences: {},
          ),
          ChoiceOption(
            id: 'leave_shrine',
            label: 'Leave the Shrine',
            description: 'Walk away',
            consequences: {},
          ),
        ],
        rewards: {'moonlight': 7},
      ),
      BuildingRoom(
        id: 'shrine_2',
        title: 'Altar Room',
        description: 'A sacred altar glows with divine energy.',
        type: RoomType.npc,
        choices: [
          ChoiceOption(
            id: 'pray',
            label: 'Pray at Altar',
            description: 'Seek blessing',
            consequences: {'moonlight': 22, 'blessing': 1},
          ),
          ChoiceOption(
            id: 'leave_altar',
            label: 'Leave Altar',
            description: 'Continue exploring',
            consequences: {'moonlight': 5},
          ),
        ],
        rewards: {'moonlight': 20},
      ),
      BuildingRoom(
        id: 'shrine_3',
        title: 'Sacred Pool',
        description: 'A crystalline pool contains pure moonlight essence.',
        type: RoomType.loot,
        choices: [
          ChoiceOption(
            id: 'bathe',
            label: 'Bathe in Pool',
            description: 'Purify yourself',
            consequences: {'moonlight': 30, 'hp_restore': 25},
          ),
          ChoiceOption(
            id: 'fill_vial',
            label: 'Fill Vials',
            description: 'Collect essence',
            consequences: {'moonlight': 35, 'essence_vial': 2},
          ),
        ],
        rewards: {'moonlight': 32},
      ),
      BuildingRoom(
        id: 'shrine_4',
        title: 'Inner Sanctum',
        description: 'At the heart of the shrine, moonlight takes physical form.',
        type: RoomType.treasure,
        choices: [
          ChoiceOption(
            id: 'commune',
            label: 'Commune with Moonlight',
            description: 'Connect spiritually',
            consequences: {'moonlight': 70, 'blessing': 2, 'knowledge': 8},
          ),
          ChoiceOption(
            id: 'claim_relic',
            label: 'Claim Sacred Relic',
            description: 'Take the artifact',
            consequences: {'moonlight': 90},
          ),
        ],
        rewards: {'moonlight': 70},
      ),
    ];
  }

  List<BuildingRoom> _generateVaultRooms() {
    return [
      BuildingRoom(
        id: 'vault_1',
        title: 'Vault Entrance',
        description: 'Massive doors inscribed with lunar runes bar the way.',
        type: RoomType.entrance,
        choices: [
          ChoiceOption(
            id: 'enter_vault',
            label: 'Enter Vault',
            description: 'Break the seal',
            consequences: {},
          ),
          ChoiceOption(
            id: 'leave_vault',
            label: 'Leave Vault',
            description: 'Respect the seal',
            consequences: {},
          ),
        ],
        rewards: {'moonlight': 12},
      ),
      BuildingRoom(
        id: 'vault_2',
        title: 'Trapped Corridor',
        description: 'Pressure plates line the floor. Ancient magic guards the way.',
        type: RoomType.hazard,
        hazardType: HazardType.fire,
        choices: [
          ChoiceOption(
            id: 'dodge_traps',
            label: 'Dodge Traps',
            description: 'Move carefully',
            consequences: {'moonlight': 18},
          ),
          ChoiceOption(
            id: 'trigger_safely',
            label: 'Trigger Safely',
            description: 'Disarm the magic',
            consequences: {'moonlight': 28, 'shadow_essence': 5},
          ),
        ],
        rewards: {'moonlight': 22},
      ),
      BuildingRoom(
        id: 'vault_3',
        title: 'Treasure Room',
        description: 'Chests overflow with lunar treasures of immense value.',
        type: RoomType.loot,
        choices: [
          ChoiceOption(
            id: 'quick_grab',
            label: 'Quick Grab',
            description: 'Take what fits',
            consequences: {'moonlight': 40, 'gold': 20},
          ),
          ChoiceOption(
            id: 'careful_sort',
            label: 'Sort Carefully',
            description: 'Choose wisely',
            consequences: {'moonlight': 60, 'gold': 30, 'gemstone': 2},
          ),
        ],
        rewards: {'moonlight': 50},
      ),
      BuildingRoom(
        id: 'vault_4',
        title: 'Vault Heart',
        description: 'The most precious treasure lies in the vault\'s heart, guarded by ancient magic.',
        type: RoomType.treasure,
        choices: [
          ChoiceOption(
            id: 'take_heart',
            label: 'Take the Heart',
            description: 'Claim ultimate treasure',
            consequences: {'moonlight': 100, 'gold': 50, 'gemstone': 5},
          ),
          ChoiceOption(
            id: 'seal_it',
            label: 'Seal It Away',
            description: 'Leave it protected',
            consequences: {'moonlight': 120, 'blessing': 3},
          ),
        ],
        rewards: {'moonlight': 100},
      ),
    ];
  }

  BuildingState createBuilding(
    String buildingType,
    String buildingName,
    int difficultyLevel,
  ) {
    final rooms = _roomTemplates[buildingType] ?? _roomTemplates['ruins']!;
    final firstRoom = rooms.first;

    final id = '${DateTime.now().millisecondsSinceEpoch}_building';

    final building = BuildingState(
      id: id,
      buildingName: buildingName,
      currentRoom: firstRoom,
      completedRooms: [],
      collectedLoot: {},
      temporaryModifiers: {'difficulty_multiplier': difficultyLevel / 10.0},
      currentDifficultyLevel: difficultyLevel,
    );

    _currentBuilding = building;
    notifyListeners();
    return building;
  }

  BuildingRoom selectNextRoom(String choiceId) {
    if (_currentBuilding == null) {
      throw StateError('No active building');
    }

    final currentRoom = _currentBuilding!.currentRoom;
    final choice = currentRoom.choices.firstWhere(
      (c) => c.id == choiceId,
      orElse: () => currentRoom.choices.first,
    );

    if (choiceId == 'turn_back' ||
        choiceId == 'leave_archive' ||
        choiceId == 'leave_ruins' ||
        choiceId == 'leave_shrine' ||
        choiceId == 'leave_vault') {
      completeBuilding(abandoned: true);
      return currentRoom;
    }

    final nextRoomId = _getNextRoomId(currentRoom.id, choiceId);
    final buildingType = _getBuildingTypeFromRoomId(currentRoom.id);
    final rooms = _roomTemplates[buildingType] ??
        _roomTemplates['ruins']!;
    final nextRoom =
        rooms.firstWhere((r) => r.id.endsWith('_${nextRoomId.split('_').last}'));

    final newCompletedRooms = [..._currentBuilding!.completedRooms, currentRoom];
    final newLoot = _applyRoomRewards(choice.consequences);

    final isLastRoom = nextRoomId.endsWith('_4');

    updateBuildingState(
      currentRoom: nextRoom,
      completedRooms: newCompletedRooms,
      collectedLoot: newLoot,
      isCombatTriggered: choice.consequences.containsKey('requires_combat'),
    );

    if (isLastRoom) {
      completeBuilding();
    }

    return nextRoom;
  }

  Map<String, int> _applyRoomRewards(Map<String, dynamic> consequences) {
    final loot = Map<String, int>.from(_currentBuilding!.collectedLoot);

    for (final entry in consequences.entries) {
      if (entry.key != 'requires_combat' && entry.value is int) {
        loot[entry.key] = (loot[entry.key] ?? 0) + (entry.value as int);
      }
    }

    return loot;
  }

  String _getNextRoomId(String currentId, String choiceId) {
    final parts = currentId.split('_');
    final buildingType = parts[0];
    final roomNum = int.parse(parts[1]);

    final nextNum = roomNum < 4 ? roomNum + 1 : 4;
    return '${buildingType}_$nextNum';
  }

  String _getBuildingTypeFromRoomId(String roomId) {
    final parts = roomId.split('_');
    if (parts.isNotEmpty) {
      return parts[0];
    }
    return 'ruins';
  }

  void updateBuildingState({
    BuildingRoom? currentRoom,
    List<BuildingRoom>? completedRooms,
    Map<String, int>? collectedLoot,
    Map<String, dynamic>? temporaryModifiers,
    bool? isCombatTriggered,
  }) {
    if (_currentBuilding == null) return;

    _currentBuilding = _currentBuilding!.copyWith(
      currentRoom: currentRoom,
      completedRooms: completedRooms,
      collectedLoot: collectedLoot,
      temporaryModifiers: temporaryModifiers,
      isCombatTriggered: isCombatTriggered,
    );

    notifyListeners();
  }

  void completeBuilding({bool abandoned = false}) {
    if (_currentBuilding == null) return;

    _currentBuilding = _currentBuilding!.copyWith(
      isCompleted: true,
    );

    notifyListeners();
  }

  BuildingState? getCurrentBuilding() {
    return _currentBuilding;
  }

  Map<String, int> getBuildingResults() {
    if (_currentBuilding == null) {
      return {};
    }

    final rewards = Map<String, int>.from(_currentBuilding!.collectedLoot);
    final baseBonus =
        (50 * (_currentBuilding!.currentDifficultyLevel / 10.0)).round();
    rewards['moonlight'] = (rewards['moonlight'] ?? 0) + baseBonus;

    return rewards;
  }

  void resetBuilding() {
    _currentBuilding = null;
    notifyListeners();
  }
}
