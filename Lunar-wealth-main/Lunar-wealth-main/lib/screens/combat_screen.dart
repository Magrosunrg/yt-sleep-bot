import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../services/lunar_game_service.dart';
import '../services/combat_service.dart';
import '../services/map_service.dart';
import '../models/combat_state.dart';

class CombatScreen extends StatefulWidget {
  final String enemyId;
  final String? locationId;
  final String? regionId;

  const CombatScreen({
    super.key, 
    required this.enemyId, 
    this.locationId,
    this.regionId,
  });

  @override
  State<CombatScreen> createState() => _CombatScreenState();
}

class _CombatScreenState extends State<CombatScreen> {
  bool _victoryProcessed = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final combatService = Provider.of<CombatService>(context, listen: false);
      if (!combatService.isInCombat) {
        combatService.startCombat(widget.enemyId);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF000000),
      appBar: AppBar(
        backgroundColor: const Color(0xFF000000),
        title: const Text(
          'COMBAT',
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: 18,
            fontWeight: FontWeight.bold,
            letterSpacing: 2.0,
            color: Color(0xFFFFFFFF),
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFFFFFFFF)),
          onPressed: () {
            final combatService = Provider.of<CombatService>(context, listen: false);
            combatService.endCombat();
            Navigator.of(context).pop();
          },
        ),
      ),
      body: Consumer2<CombatService, LunarGameService>(
        builder: (context, combatService, gameService, child) {
          if (!combatService.isInCombat || combatService.combatState.enemy == null) {
            return _buildLoadingScreen();
          }

          final combatState = combatService.combatState;
          
          if (combatState.status == CombatStatus.victory) {
            if (widget.regionId != null && !_victoryProcessed) {
              _victoryProcessed = true;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) {
                  Provider.of<MapService>(context, listen: false).markRegionCleared(widget.regionId!);
                }
              });
            }
            return _buildVictoryScreen(combatService);
          }
          
          if (combatState.status == CombatStatus.defeat) {
            return _buildDefeatScreen(combatService);
          }

          return _buildCombatScreen(combatService, gameService);
        },
      ),
    );
  }

  Widget _buildLoadingScreen() {
    return const Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'INITIALIZING COMBAT...',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 16,
              color: Color(0xFFFFFFFF),
              letterSpacing: 2.0,
            ),
          ),
          SizedBox(height: 20),
          CircularProgressIndicator(color: Color(0xFFFFFFFF)),
        ],
      ),
    );
  }

  Widget _buildCombatScreen(CombatService combatService, LunarGameService gameService) {
    final enemy = combatService.combatState.enemy!;
    final player = gameService.playerState;
    final combatState = combatService.combatState;

    return Container(
      color: const Color(0xFF000000),
      child: Column(
        children: [
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Turn indicator
                  _buildTurnIndicator(combatState),
                  const SizedBox(height: 16),
                  
                  // Enemy section
                  _buildEnemySection(enemy, combatService),
                  const SizedBox(height: 16),
                  
                  // Battle log
                  _buildBattleLog(combatState),
                  const SizedBox(height: 16),
                  
                  // Player section
                  _buildPlayerSection(player),
                ],
              ),
            ),
          ),
          
          // Action buttons (fixed at bottom)
          if (combatState.status == CombatStatus.active)
            _buildActionButtons(combatService, gameService),
        ],
      ),
    );
  }

  Widget _buildTurnIndicator(CombatState combatState) {
    final isPlayerTurn = combatState.isPlayerTurn;
    final turnText = isPlayerTurn ? 'YOUR TURN' : 'ENEMY TURN';
    final turnColor = isPlayerTurn ? const Color(0xFF4CAF50) : const Color(0xFFFF6B6B);
    
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF000000),
        border: Border.all(color: turnColor, width: 2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            isPlayerTurn ? Icons.arrow_forward : Icons.shield,
            color: turnColor,
            size: 20,
          ),
          const SizedBox(width: 8),
          Text(
            turnText,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: turnColor,
              letterSpacing: 3.0,
            ),
          ),
          const SizedBox(width: 8),
          Icon(
            isPlayerTurn ? Icons.arrow_forward : Icons.shield,
            color: turnColor,
            size: 20,
          ),
        ],
      ),
    );
  }

  Widget _buildEnemySection(dynamic enemy, CombatService combatService) {
    final defeatCount = combatService.getDefeatCount(enemy.blueprint.id);
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF000000),
        border: Border.all(color: const Color(0xFFFFFFFF), width: 2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        children: [
          // Enemy label
          const Text(
            '═══ ENEMY ═══',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 12,
              color: Color(0xFFFFFFFF),
              letterSpacing: 2.0,
            ),
          ),
          const SizedBox(height: 12),
          
          // Enemy ASCII art
          Container(
            padding: const EdgeInsets.all(8),
            child: Text(
              enemy.blueprint.asciiArt,
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 9,
                color: Color(0xFFFF6B6B),
                height: 1.0,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 12),
          
          // Enemy name
          Text(
            enemy.blueprint.name.toUpperCase(),
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFFFFFF),
              letterSpacing: 2.0,
            ),
          ),
          
          if (defeatCount > 0) ...[
            const SizedBox(height: 4),
            Text(
              'Enhanced (x${defeatCount + 1})',
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 11,
                color: Color(0xFFFFAA00),
              ),
            ),
          ],
          
          const SizedBox(height: 16),
          
          // Enemy stats
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildStatBadge('ATK', '${enemy.minDamage}-${enemy.maxDamage}'),
              const SizedBox(width: 16),
              _buildStatBadge('SPD', '${enemy.blueprint.attackSpeed}'),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // HP bar
          _buildHpBar(
            enemy.currentHp,
            enemy.maxHp,
            const Color(0xFFFF6B6B),
          ),
          const SizedBox(height: 8),
          Text(
            'HP: ${enemy.currentHp} / ${enemy.maxHp}',
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              color: Color(0xFFFFFFFF),
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPlayerSection(dynamic player) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF000000),
        border: Border.all(color: const Color(0xFFFFFFFF), width: 2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        children: [
          // Player label
          const Text(
            '═══ PLAYER ═══',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 12,
              color: Color(0xFFFFFFFF),
              letterSpacing: 2.0,
            ),
          ),
          const SizedBox(height: 12),
          
          // Player ASCII art
          Container(
            padding: const EdgeInsets.all(8),
            child: const Text(
              '''
    O
   /|\\
   / \\
  ''',
              style: TextStyle(
                fontFamily: 'Courier',
                fontSize: 10,
                color: Color(0xFF4CAF50),
                height: 1.0,
              ),
              textAlign: TextAlign.center,
            ),
          ),
          const SizedBox(height: 12),
          
          // Player name
          Text(
            player.playerName.toUpperCase(),
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFFFFFF),
              letterSpacing: 2.0,
            ),
          ),
          
          const SizedBox(height: 16),
          
          // Player stats
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildStatBadge('ATK', '${player.baseDamage}'),
              const SizedBox(width: 12),
              _buildStatBadge('DEF', '${player.baseDefense}'),
              const SizedBox(width: 12),
              _buildStatBadge('CRIT', '${(player.critRate * 100).toInt()}%'),
            ],
          ),
          
          const SizedBox(height: 16),
          
          // HP bar
          _buildHpBar(
            player.hp,
            player.maxHp,
            const Color(0xFF4CAF50),
          ),
          const SizedBox(height: 8),
          Text(
            'HP: ${player.hp} / ${player.maxHp}',
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              color: Color(0xFFFFFFFF),
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatBadge(String label, String value) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFFFFFFFF)),
        borderRadius: BorderRadius.circular(2),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 10,
              color: Color(0xFFAAAAAA),
            ),
          ),
          Text(
            value,
            style: const TextStyle(
              fontFamily: 'Courier',
              fontSize: 12,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFFFFFF),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHpBar(int currentHp, int maxHp, Color barColor) {
    final hpPercent = currentHp / maxHp;
    
    return Column(
      children: [
        Container(
          height: 24,
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFFFFFFFF), width: 2),
            borderRadius: BorderRadius.circular(2),
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(1),
            child: Stack(
              children: [
                Container(
                  color: const Color(0xFF000000),
                ),
                FractionallySizedBox(
                  widthFactor: hpPercent.clamp(0.0, 1.0),
                  child: Container(
                    color: barColor,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildBattleLog(CombatState combatState) {
    final log = combatState.combatLog;
    final recentLogs = log.length > 5 ? log.sublist(log.length - 5) : log;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFF000000),
        border: Border.all(color: const Color(0xFFFFFFFF), width: 2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '═══ BATTLE LOG ═══',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 12,
              color: Color(0xFFFFFFFF),
              letterSpacing: 2.0,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            height: 120,
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFF444444)),
              borderRadius: BorderRadius.circular(2),
            ),
            child: SingleChildScrollView(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: recentLogs.map((logEntry) {
                  Color textColor = const Color(0xFFFFFFFF);
                  
                  if (logEntry.contains('VICTORY') || logEntry.contains('defeated')) {
                    textColor = const Color(0xFF4CAF50);
                  } else if (logEntry.contains('DEFEAT') || logEntry.contains('fallen')) {
                    textColor = const Color(0xFFFF6B6B);
                  } else if (logEntry.contains('CRITICAL')) {
                    textColor = const Color(0xFFFFD700);
                  } else if (logEntry.contains('YOUR TURN')) {
                    textColor = const Color(0xFF4CAF50);
                  } else if (logEntry.contains('ENEMY TURN')) {
                    textColor = const Color(0xFFFF6B6B);
                  }
                  
                  return Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Text(
                      logEntry,
                      style: TextStyle(
                        fontFamily: 'Courier',
                        fontSize: 11,
                        color: textColor,
                        height: 1.3,
                      ),
                    ),
                  );
                }).toList(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionButtons(CombatService combatService, LunarGameService gameService) {
    final canAct = combatService.combatState.isPlayerTurn && 
                   !combatService.combatState.isProcessingAction;
    final player = gameService.playerState;
    final canHeal = player.moonlight >= 20 && player.hp < player.maxHp;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: const BoxDecoration(
        color: Color(0xFF000000),
        border: Border(
          top: BorderSide(color: Color(0xFFFFFFFF), width: 2),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              Expanded(
                child: _buildActionButton(
                  label: '[A] ATTACK',
                  icon: Icons.gps_fixed,
                  onPressed: canAct ? () => combatService.playerAttack() : null,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: _buildActionButton(
                  label: '[G] GUARD',
                  icon: Icons.shield,
                  onPressed: canAct ? () => combatService.playerGuard() : null,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          _buildActionButton(
            label: '[U] USE ITEM (Heal: 20 Moonlight)',
            icon: Icons.healing,
            onPressed: (canAct && canHeal) 
                ? () => combatService.playerUseItem('heal')
                : null,
            fullWidth: true,
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton({
    required String label,
    required IconData icon,
    required VoidCallback? onPressed,
    bool fullWidth = false,
  }) {
    final isEnabled = onPressed != null;
    
    return SizedBox(
      width: fullWidth ? double.infinity : null,
      height: 48,
      child: ElevatedButton(
        onPressed: onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: isEnabled ? const Color(0xFF000000) : const Color(0xFF1A1A1A),
          foregroundColor: isEnabled ? const Color(0xFFFFFFFF) : const Color(0xFF666666),
          side: BorderSide(
            color: isEnabled ? const Color(0xFFFFFFFF) : const Color(0xFF444444),
            width: 2,
          ),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icon, size: 20),
            const SizedBox(width: 8),
            Text(
              label,
              style: const TextStyle(
                fontFamily: 'Courier',
                fontSize: 12,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildVictoryScreen(CombatService combatService) {
    final log = combatService.combatState.combatLog;
    final victoryLog = log.where((line) => 
      line.contains('VICTORY') || 
      line.contains('earned') || 
      line.contains('Found:')
    ).toList();
    
    return Container(
      color: const Color(0xFF000000),
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.emoji_events,
            size: 80,
            color: Color(0xFFFFD700),
          ),
          const SizedBox(height: 24),
          const Text(
            '╔═══════════════════════╗',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              color: Color(0xFFFFFFFF),
            ),
            textAlign: TextAlign.center,
          ),
          const Text(
            '║       VICTORY!       ║',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Color(0xFF4CAF50),
              letterSpacing: 2.0,
            ),
            textAlign: TextAlign.center,
          ),
          const Text(
            '╚═══════════════════════╝',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              color: Color(0xFFFFFFFF),
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFFFFFFFF), width: 2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'REWARDS:',
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 14,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFFFFFFFF),
                    letterSpacing: 2.0,
                  ),
                ),
                const SizedBox(height: 12),
                ...victoryLog.map((line) => Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: Text(
                    line,
                    style: const TextStyle(
                      fontFamily: 'Courier',
                      fontSize: 13,
                      color: Color(0xFFFFD700),
                    ),
                  ),
                )),
              ],
            ),
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: () {
                combatService.endCombat();
                Navigator.of(context).pop();
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF000000),
                foregroundColor: const Color(0xFFFFFFFF),
                side: const BorderSide(color: Color(0xFF4CAF50), width: 2),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              child: const Text(
                'CONTINUE',
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 2.0,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDefeatScreen(CombatService combatService) {
    return Container(
      color: const Color(0xFF000000),
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(
            Icons.dangerous,
            size: 80,
            color: Color(0xFFFF6B6B),
          ),
          const SizedBox(height: 24),
          const Text(
            '╔═══════════════════════╗',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              color: Color(0xFFFFFFFF),
            ),
            textAlign: TextAlign.center,
          ),
          const Text(
            '║       DEFEAT...      ║',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: Color(0xFFFF6B6B),
              letterSpacing: 2.0,
            ),
            textAlign: TextAlign.center,
          ),
          const Text(
            '╚═══════════════════════╝',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: 14,
              color: Color(0xFFFFFFFF),
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 32),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              border: Border.all(color: const Color(0xFFFF6B6B), width: 2),
              borderRadius: BorderRadius.circular(4),
            ),
            child: const Column(
              children: [
                Text(
                  'You have been defeated...',
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 14,
                    color: Color(0xFFFFFFFF),
                  ),
                  textAlign: TextAlign.center,
                ),
                SizedBox(height: 8),
                Text(
                  'Train harder and try again!',
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: 12,
                    color: Color(0xFFAAAAAA),
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            height: 56,
            child: ElevatedButton(
              onPressed: () {
                combatService.endCombat();
                Navigator.of(context).pop();
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF000000),
                foregroundColor: const Color(0xFFFFFFFF),
                side: const BorderSide(color: Color(0xFFFF6B6B), width: 2),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              child: const Text(
                'RETREAT',
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 2.0,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
