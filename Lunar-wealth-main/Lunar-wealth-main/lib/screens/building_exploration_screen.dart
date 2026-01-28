import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../services/building_service.dart';
import '../services/exploration_log_service.dart';
import '../services/lunar_game_service.dart';
import '../models/building_state.dart';
import '../models/building_room.dart';
import '../models/choice_option.dart';

class BuildingExplorationScreen extends StatefulWidget {
  final String buildingType;
  final String buildingName;

  const BuildingExplorationScreen({
    super.key,
    required this.buildingType,
    required this.buildingName,
  });

  @override
  State<BuildingExplorationScreen> createState() =>
      _BuildingExplorationScreenState();
}

class _BuildingExplorationScreenState extends State<BuildingExplorationScreen> {
  late BuildingService _buildingService;
  BuildingState? _buildingState;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _initializeBuilding();
  }

  void _initializeBuilding() {
    _buildingService = context.read<BuildingService>();
    final logService = context.read<ExplorationLogService>();

    logService.pauseExploration();

    final difficulty = logService.currentDifficultyLevel;
    _buildingState = _buildingService.createBuilding(
      widget.buildingType,
      widget.buildingName,
      difficulty,
    );

    setState(() {
      _isLoading = false;
    });
  }

  void _handleChoice(ChoiceOption choice) {
    if (_buildingState == null) return;

    final nextRoom = _buildingService.selectNextRoom(choice.id);

    if (nextRoom == _buildingState!.currentRoom &&
        (choice.id == 'turn_back' ||
            choice.id == 'leave_archive' ||
            choice.id == 'leave_ruins' ||
            choice.id == 'leave_shrine' ||
            choice.id == 'leave_vault')) {
      _exitBuilding(abandoned: true);
    } else if (_buildingService.getCurrentBuilding()?.isCompleted ?? false) {
      _exitBuilding();
    } else {
      setState(() {
        _buildingState = _buildingService.getCurrentBuilding();
      });
    }
  }

  void _exitBuilding({bool abandoned = false}) {
    if (!mounted) return;

    final buildingService = context.read<BuildingService>();
    final logService = context.read<ExplorationLogService>();
    final gameService = context.read<LunarGameService>();

    final results = buildingService.getBuildingResults();

    String exitMessage = abandoned
        ? 'You left the ${widget.buildingName} and returned to exploration.'
        : 'You have completed the ${widget.buildingName}!';

    String rewardSummary = 'Rewards earned: ';
    rewardSummary +=
        results.entries.map((e) => '${e.key}: +${e.value}').join(', ');

    for (final entry in results.entries) {
      if (entry.key == 'moonlight') {
        gameService.addMoonlight(entry.value);
      } else {
        gameService.addResource(entry.key, entry.value);
      }
    }

    logService.appendBuildingResultEntry(
      abandoned ? 'LEFT BUILDING' : 'COMPLETED BUILDING',
      '$exitMessage\n$rewardSummary',
      results,
    );

    buildingService.resetBuilding();
    logService.resumeExploration();

    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading || _buildingState == null) {
      return const Scaffold(
        backgroundColor: Color(0xFF000000),
        body: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              SizedBox(height: 20),
              Text(
                'ENTERING BUILDING...',
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: Color(0xFFFFD700),
                ),
              ),
              SizedBox(height: 20),
              CircularProgressIndicator(
                valueColor: AlwaysStoppedAnimation<Color>(Color(0xFFFFD700)),
              ),
            ],
          ),
        ),
      );
    }

    final currentRoom = _buildingState!.currentRoom;

    return Scaffold(
      backgroundColor: const Color(0xFF000000),
      body: SafeArea(
        child: Column(
          children: [
            _buildHeader(),
            const SizedBox(height: 8),
            Expanded(
              child: _buildRoomDisplay(currentRoom),
            ),
            const SizedBox(height: 8),
            _buildChoicesPanel(currentRoom),
          ],
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF333333)),
        color: const Color(0xFF0F0F23),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _buildingState!.buildingName.toUpperCase(),
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFFD700),
            ),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _buildStatChip(
                'ROOM',
                '${_buildingState!.roomCount + 1}/4',
                Colors.cyan,
              ),
              _buildStatChip(
                'LOOT COLLECTED',
                _buildingState!.totalLoot.toString(),
                Colors.green,
              ),
              _buildStatChip(
                'DIFFICULTY',
                'L${_buildingState!.currentDifficultyLevel}',
                Colors.purple,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildStatChip(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.6)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 9,
              color: Color(0xFF888888),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRoomDisplay(BuildingRoom room) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF333333)),
        color: const Color(0xFF0F0F0F),
      ),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildRoomArt(room.type, room.hazardType),
            const SizedBox(height: 16),
            Text(
              room.title.toUpperCase(),
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Color(0xFFFFD700),
              ),
            ),
            const SizedBox(height: 8),
            Text(
              room.description,
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 11,
                color: Color(0xFFCCCCCC),
              ),
            ),
            const SizedBox(height: 12),
            _buildRoomInfo(room),
          ],
        ),
      ),
    );
  }

  Widget _buildRoomArt(RoomType type, HazardType hazard) {
    const line = '┌─────────────────────────┐';
    const divider = '├─────────────────────────┤';
    const endLine = '└─────────────────────────┘';

    String art = '$line\n';

    switch (type) {
      case RoomType.entrance:
        art += '│ ◉ ═ ENTRANCE ═ ◉       │\n';
        break;
      case RoomType.hazard:
        art += switch (hazard) {
          HazardType.spike => '│ ⚠ SPIKES ⚠ ▲▲▲       │\n',
          HazardType.fire => '│ ⚠ FIRE ⚠ ~~~       │\n',
          HazardType.ice => '│ ⚠ ICE ⚠ ❆❆❆       │\n',
          HazardType.poison => '│ ⚠ POISON ⚠ ☠☠☠     │\n',
          HazardType.electricity => '│ ⚠ ELECTRIC ⚠ ⚡⚡⚡    │\n',
          HazardType.none => '│ ⚠ HAZARD ⚠          │\n',
        };
        break;
      case RoomType.loot:
        art += '│ ◆ LOOT ◆ ◆◆◆       │\n';
        break;
      case RoomType.treasure:
        art += '│ ★ TREASURE ★ ✦✦✦     │\n';
        break;
      case RoomType.npc:
        art += '│ ⊙ NPC ⊙ ◊◊◊         │\n';
        break;
      case RoomType.encounter:
        art += '│ ⚔ ENCOUNTER ⚔ ✧✧✧    │\n';
        break;
      case RoomType.boss:
        art += '│ ◈ BOSS ◈ ✦✦✦✦       │\n';
        break;
    }

    art += '$divider\n';
    art += '│  ROOM ${_buildingState!.roomCount + 1} OF 4     │\n';
    art += endLine;

    return Text(
      art,
      style: const TextStyle(
        fontFamily: 'Courier',
        fontSize: 10,
        color: Color(0xFF90EE90),
        height: 1.2,
      ),
    );
  }

  Widget _buildRoomInfo(BuildingRoom room) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF444444)),
        borderRadius: BorderRadius.circular(2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'ROOM TYPE: ${room.type.name.toUpperCase()}',
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 9,
              color: Color(0xFF888888),
            ),
          ),
          if (room.rewards.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              'BASE REWARD: ${room.rewards.entries.map((e) => '${e.key}: +${e.value}').join(', ')}',
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 9,
                color: Color(0xFF90EE90),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildChoicesPanel(BuildingRoom room) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF333333)),
        color: const Color(0xFF0F0F23),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'CHOOSE YOUR ACTION:',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 11,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFFFFFF),
            ),
          ),
          const SizedBox(height: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: room.choices.map((choice) {
              return Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: OutlinedButton(
                  onPressed: () => _handleChoice(choice),
                  style: OutlinedButton.styleFrom(
                    side: const BorderSide(color: Color(0xFFFFD700)),
                    backgroundColor:
                        const Color(0xFFFFD700).withValues(alpha: 0.05),
                    padding: const EdgeInsets.symmetric(vertical: 8),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        choice.label.toUpperCase(),
                        style: const TextStyle(
                          fontFamily: 'Courier',
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          color: Color(0xFFFFD700),
                        ),
                      ),
                      if (choice.description.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(
                          choice.description,
                          style: const TextStyle(
                            fontFamily: 'Courier',
                            fontSize: 9,
                            color: Color(0xFFCCCCCC),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    super.dispose();
  }
}
