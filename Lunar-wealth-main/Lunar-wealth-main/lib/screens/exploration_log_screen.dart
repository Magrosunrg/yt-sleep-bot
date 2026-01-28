import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';

import '../utils/color_extensions.dart';
import '../services/exploration_log_service.dart';
import '../services/combat_service.dart';

import '../models/choice_option.dart';
import '../models/log_entry.dart';
import 'combat_screen.dart';
import 'building_exploration_screen.dart';

class ExplorationLogScreen extends StatefulWidget {
  const ExplorationLogScreen({super.key});

  @override
  State<ExplorationLogScreen> createState() => _ExplorationLogScreenState();
}

class _ExplorationLogScreenState extends State<ExplorationLogScreen> {
  final ScrollController _logScrollController = ScrollController();
  static const double _topBarHeight = 40;
  static const double _bottomBarHeight = 88;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final logService = context.read<ExplorationLogService>();
      if (!logService.isExploring) {
        logService.startExploration();
      }
      _scrollToBottom();
    });
  }

  @override
  void dispose() {
    _logScrollController.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    if (_logScrollController.hasClients) {
      _logScrollController.animateTo(
        _logScrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  void _handleChoice(
    BuildContext context,
    ExplorationLogEntry entry,
    ChoiceOption choice,
  ) {
    final logService = context.read<ExplorationLogService>();

    if (choice.id == 'flee') {
      logService.resolveLogEntry(entry.id, choice.id);
      logService.resumeExploration();
      return;
    }

    if (choice.consequences.containsKey('requires_building')) {
      _handleBuildingEntry(context, entry, choice);
    } else if (entry.encounterContext != null &&
        choice.consequences.containsKey('requires_combat') &&
        entry.encounterContext!.isSoloEncounter) {
      _handleSoloEncounter(context, entry, choice);
    } else if (entry.encounterContext != null &&
        choice.consequences.containsKey('requires_combat') &&
        !entry.encounterContext!.isSoloEncounter) {
      _handleMultiEnemyEncounter(context, entry, choice);
    } else {
      logService.resolveLogEntry(entry.id, choice.id);
      logService.resumeExploration();
    }
  }

  void _handleBuildingEntry(
    BuildContext context,
    ExplorationLogEntry entry,
    ChoiceOption choice,
  ) {
    if (choice.id != 'enter_building') {
      final logService = context.read<ExplorationLogService>();
      logService.resolveLogEntry(entry.id, choice.id);
      logService.resumeExploration();
      return;
    }

    final buildingType = entry.eventData['building_type'] as String? ?? 'ruins';
    final logService = context.read<ExplorationLogService>();

    Navigator.of(context)
        .push(
      MaterialPageRoute(
        builder: (context) => BuildingExplorationScreen(
          buildingType: buildingType,
          buildingName: entry.title,
        ),
      ),
    )
        .then((_) {
      if (mounted) {
        logService.resolveLogEntry(entry.id, choice.id);
      }
    });
  }

  void _handleSoloEncounter(
    BuildContext context,
    ExplorationLogEntry entry,
    ChoiceOption choice,
  ) {
    final logService = context.read<ExplorationLogService>();
    final combatService = context.read<CombatService>();

    final enemyName = entry.title;
    final enemyStats = {
      'name': enemyName,
      'hp': 20,
      'defense': 2,
      'damage': 3,
    };

    final result = combatService.resolveSoloEncounter(
      entry.encounterContext!,
      enemyStats,
    );

    final damageDealt = result['playerDamageDealt'] as int;
    final isCritical = result['isCritical'] as bool;
    final resourcesEarned = result['resourcesEarned'] as Map<String, dynamic>;

    String resultText = isCritical
        ? 'CRITICAL HIT: You strike $enemyName for $damageDealt damage!'
        : 'You strike $enemyName for $damageDealt damage.';

    resultText += ' Enemy defeated! Resources earned: ';
    resultText +=
        resourcesEarned.entries.map((e) => '${e.key}: ${e.value}').join(', ');

    combatService.awardRewards(resourcesEarned.cast<String, int>());

    logService.appendCombatResultEntry(
      'SOLO ENCOUNTER: $enemyName',
      resultText,
      resourcesEarned.cast<String, int>(),
      entry.encounterContext,
    );

    logService.resolveLogEntry(entry.id, choice.id);
    logService.resumeExploration();
  }

  void _handleMultiEnemyEncounter(
    BuildContext context,
    ExplorationLogEntry entry,
    ChoiceOption choice,
  ) {
    final logService = context.read<ExplorationLogService>();
    final combatService = context.read<CombatService>();

    final multiEnemySetup =
        combatService.calculateMultiEnemyEncounter(entry.encounterContext!);

    final enemies =
        List<Map<String, dynamic>>.from(multiEnemySetup['enemies'] as List);

    Navigator.of(context)
        .push(
      MaterialPageRoute(
        builder: (context) => CombatScreen(
          encounterContext: entry.encounterContext!,
          enemies: enemies,
          encounterTitle: entry.title,
        ),
      ),
    )
        .then((_) {
      if (mounted) {
        logService.resolveLogEntry(entry.id, choice.id);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: const Color(0xFF000000),
        body: SafeArea(
          child: Column(
            children: [
              _buildTopBar(),
              _buildLogPanel(context),
              _buildBottomBar(context),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      height: _topBarHeight,
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      alignment: Alignment.centerLeft,
      decoration: const BoxDecoration(
        color: Color(0xFF050505),
        border: Border(
          bottom: BorderSide(color: Color(0xFF333333), width: 2),
        ),
      ),
      child: const Text(
        'system logs',
        style: TextStyle(
          fontFamily: 'Courier',
          fontSize: 14,
          fontWeight: FontWeight.bold,
          letterSpacing: 3,
          color: Color(0xFFFFD700),
        ),
      ),
    );
  }

  Widget _buildLogPanel(BuildContext context) {
    return Expanded(
      child: Container(
        width: double.infinity,
        color: const Color(0xFF000000),
        child: Consumer<ExplorationLogService>(
          builder: (context, logService, child) {
            final logHistory = logService.logHistory;

            if (logHistory.isEmpty) {
              return _buildEmptyState();
            }

            WidgetsBinding.instance
                .addPostFrameCallback((_) => _scrollToBottom());

            final latestEntry = logHistory.isNotEmpty ? logHistory.last : null;
            final bool showChoices = latestEntry != null &&
                !latestEntry.isResolved &&
                latestEntry.choices.isNotEmpty;

            final logWidgets = <Widget>[];

            for (var i = 0; i < logHistory.length; i++) {
              final entry = logHistory[i];
              final isLatest = i == logHistory.length - 1;

              logWidgets.add(
                LogEntryWidget(
                  entry: entry,
                  isLatest: isLatest,
                ),
              );

              if (showChoices && isLatest) {
                logWidgets.add(const SizedBox(height: 8));
                logWidgets.addAll(entry.choices.map(
                  (choice) => Padding(
                    padding: const EdgeInsets.only(bottom: 6),
                    child: ChoiceButtonWidget(
                      choice: choice,
                      onPressed: () {
                        HapticFeedback.lightImpact();
                        _handleChoice(context, entry, choice);
                      },
                    ),
                  ),
                ));
              }
            }

            return Container(
              margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFF050505),
                border: Border.all(color: const Color(0xFF252525), width: 2),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.45),
                    offset: const Offset(0, 6),
                    blurRadius: 12,
                  ),
                ],
              ),
              child: ListView(
                controller: _logScrollController,
                padding:
                    const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                children: logWidgets,
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildEmptyState() {
    return const Center(
      child: Padding(
        padding: EdgeInsets.symmetric(horizontal: 32),
        child: Text(
          '''
┌──────────────────────────────────────┐
│   awaiting lunar telemetry feed...   │
│   expedition initializing shortly.   │
└──────────────────────────────────────┘
''',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 12,
            height: 1.2,
            color: Color(0xFF666666),
          ),
        ),
      ),
    );
  }

  Widget _buildBottomBar(BuildContext context) {
    return Consumer<ExplorationLogService>(
      builder: (context, logService, child) {
        final bool isPaused = logService.isPaused;
        final bool isExploring = logService.isExploring;

        String primaryLabel = '[PAUSE EXPEDITION]';
        if (!isExploring) {
          primaryLabel = '[BEGIN EXPEDITION]';
        } else if (isPaused) {
          primaryLabel = '[RESUME EXPEDITION]';
        }

        return Container(
          height: _bottomBarHeight,
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
          decoration: BoxDecoration(
            color: const Color(0xFF05050F),
            border: Border.all(color: const Color(0xFF333333), width: 3),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.6),
                offset: const Offset(0, -4),
                blurRadius: 12,
              ),
            ],
          ),
          child: Row(
            children: [
              Expanded(
                child: _buildSystemButton(
                  label: primaryLabel,
                  color: const Color(0xFFFFD700),
                  onPressed: () => _onPrimaryAction(logService),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: _buildSystemButton(
                  label: '[RETURN HOME]',
                  color: const Color(0xFFFF6B6B),
                  onPressed: () => _handleReturnHome(context),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _onPrimaryAction(ExplorationLogService logService) {
    if (!logService.isExploring) {
      logService.startExploration();
      return;
    }

    if (logService.isPaused) {
      logService.resumeExploration();
    } else {
      logService.pauseExploration();
    }
  }

  void _handleReturnHome(BuildContext context) {
    final logService = context.read<ExplorationLogService>();
    logService.stopExploration();
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  Widget _buildSystemButton({
    required String label,
    required Color color,
    required VoidCallback onPressed,
  }) {
    return SizedBox.expand(
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color, width: 2),
          backgroundColor: color.withValues(alpha: 0.12),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(4)),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 12,
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
            color: color,
          ),
        ),
      ),
    );
  }
}

class LogEntryWidget extends StatelessWidget {
  final ExplorationLogEntry entry;
  final bool isLatest;

  const LogEntryWidget({
    super.key,
    required this.entry,
    required this.isLatest,
  });

  @override
  Widget build(BuildContext context) {
    final timestamp = _formatElapsedTime(entry.elapsedTimeSeconds);
    final message = _buildMessage(entry);

    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 4),
      decoration: BoxDecoration(
        color: isLatest ? const Color(0xFF121214) : Colors.transparent,
        borderRadius: BorderRadius.circular(2),
      ),
      child: RichText(
        text: TextSpan(
          style: const TextStyle(
            fontFamily: 'Courier',
            fontSize: 12,
            height: 1.3,
            color: Color(0xFFCCCCCC),
          ),
          children: [
            TextSpan(
              text: '[$timestamp] ',
              style: const TextStyle(
                color: Color(0xFF888888),
              ),
            ),
            TextSpan(
              text: message,
              style: const TextStyle(
                color: Color(0xFFEEEEEE),
              ),
            ),
          ],
        ),
      ),
    );
  }

  String _formatElapsedTime(int elapsedSeconds) {
    final clampedSeconds = elapsedSeconds < 0
        ? 0
        : (elapsedSeconds > 359999 ? 359999 : elapsedSeconds);
    final hours = (clampedSeconds ~/ 3600).toString().padLeft(2, '0');
    final minutes = ((clampedSeconds % 3600) ~/ 60).toString().padLeft(2, '0');
    final seconds = (clampedSeconds % 60).toString().padLeft(2, '0');
    return '$hours:$minutes:$seconds';
  }

  String _buildMessage(ExplorationLogEntry entry) {
    final hasDescription = entry.description.trim().isNotEmpty;
    final sanitizedDescription = hasDescription
        ? entry.description
            .replaceAll('\n', ' ')
            .replaceAll(RegExp(r'\s+'), ' ')
            .trim()
        : entry.title;
    final buffer = StringBuffer(sanitizedDescription);

    if (entry.rewards.isNotEmpty) {
      final rewardSummary = entry.rewards.entries
          .map((e) =>
              '${e.key.toUpperCase()}: ${e.value >= 0 ? '+${e.value}' : e.value}')
          .join(', ');
      buffer.write(' {Rewards: $rewardSummary}');
    }

    if (entry.isResolved) {
      buffer.write(
          ' [Resolved: ${(entry.chosenOptionId ?? 'unknown').toUpperCase()}]');
    }

    return buffer.toString();
  }
}

class ChoiceButtonWidget extends StatelessWidget {
  final ChoiceOption choice;
  final VoidCallback onPressed;

  const ChoiceButtonWidget({
    super.key,
    required this.choice,
    required this.onPressed,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          side: const BorderSide(color: Color(0xFF666666)),
          backgroundColor: const Color(0xFF1A1A2E),
          padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 16),
          alignment: Alignment.centerLeft,
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              choice.label,
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 12,
                color: Color(0xFFFFFFFF),
                fontWeight: FontWeight.bold,
              ),
            ),
            if (choice.consequences.isNotEmpty) ...[
              const SizedBox(height: 2),
              Text(
                choice.consequences.entries
                    .map((e) =>
                        '${e.key.toUpperCase()}: ${e.value > 0 ? '+' : ''}${e.value}')
                    .join(', '),
                style: const TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 10,
                  color: Color(0xFFAAAAAA),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
