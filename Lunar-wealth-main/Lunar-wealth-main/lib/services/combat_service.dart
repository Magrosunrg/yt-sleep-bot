import 'dart:math';
import 'package:flutter/foundation.dart';
import '../models/encounter_context.dart';
import 'lunar_game_service.dart';

class CombatResult {
  final bool victory;
  final List<String> combatLog;
  final int damageDealt;
  final int damageTaken;
  final Map<String, int> rewardsEarned;
  final int monstersDefeated;

  const CombatResult({
    required this.victory,
    required this.combatLog,
    required this.damageDealt,
    required this.damageTaken,
    required this.rewardsEarned,
    required this.monstersDefeated,
  });
}

class CombatService extends ChangeNotifier {
  final LunarGameService _gameService;
  final Random _random = Random();

  static const int damageVariance = 5;
  static const int maxRoundsPerCombat = 50;

  CombatService(this._gameService);

  Map<String, dynamic> resolveSoloEncounter(
    EncounterContext context,
    Map<String, dynamic> enemyStats,
  ) {
    final playerDamage = (_gameService.playerState.baseDamage +
            _random.nextInt(damageVariance) -
            (damageVariance ~/ 2))
        .clamp(1, 999999);

    final enemyDefense = (enemyStats['defense'] as int?) ?? 2;
    final damageTaken =
        (playerDamage - enemyDefense).clamp(1, playerDamage);

    final playerCritChance = _gameService.playerState.critRate;
    final isCritical = _random.nextDouble() < playerCritChance;
    final finalDamage = isCritical ? (damageTaken * 1.5).round() : damageTaken;

    const int monstersDefeated = 1;
    final resourcesEarned = _calculateEncounterRewards(context, monstersDefeated);

    return {
      'won': true,
      'playerDamageDealt': finalDamage,
      'isCritical': isCritical,
      'monstersDefeated': monstersDefeated,
      'resourcesEarned': resourcesEarned,
      'enemyName': enemyStats['name'] as String? ?? 'Unknown Enemy',
    };
  }

  Map<String, int> _calculateEncounterRewards(
    EncounterContext context,
    int monstersDefeated,
  ) {
    final baseRewards = <String, int>{
      'moonlight': 10 * context.difficultyLevel * monstersDefeated,
      'shadow_essence': (2 * monstersDefeated).clamp(1, 10),
      'lunar_claw': monstersDefeated.clamp(0, 3),
    };

    final scaledRewards = <String, int>{};
    for (final entry in baseRewards.entries) {
      final scaling =
          (context.resourceScaling[entry.key] ?? 100) / 100.0;
      scaledRewards[entry.key] = (entry.value * scaling).round();
    }

    return scaledRewards;
  }

  Map<String, dynamic> calculateMultiEnemyEncounter(
    EncounterContext context,
  ) {
    final enemyCount =
        context.minEnemies + _random.nextInt(context.maxEnemies - context.minEnemies + 1);

    final enemies = List.generate(enemyCount, (index) {
      final hp = 15 + (context.difficultyLevel * 5);
      final defense = 1 + (context.difficultyLevel ~/ 2);
      return {
        'id': 'enemy_$index',
        'name': 'Shadow Beast ${index + 1}',
        'hp': hp,
        'defense': defense,
        'damage': 3 + context.difficultyLevel,
      };
    });

    return {
      'enemyCount': enemyCount,
      'enemies': enemies,
      'estimatedRewards': _calculateEncounterRewards(context, enemyCount),
    };
  }

  CombatResult resolveMultiEnemyCombat(
    EncounterContext context,
    List<Map<String, dynamic>> enemies,
  ) {
    final combatLog = <String>[];
    int totalDamageDealt = 0;
    int totalDamageTaken = 0;
    int monstersDefeated = 0;
    final enemyCopies = enemies.map((e) => Map<String, dynamic>.from(e)).toList();

    for (int round = 0; round < maxRoundsPerCombat; round++) {
      if (enemyCopies.isEmpty) break;

      // Player attacks
      for (int i = 0; i < enemyCopies.length; i++) {
        final enemy = enemyCopies[i];
        final playerDamage = (_gameService.playerState.baseDamage +
                _random.nextInt(damageVariance) -
                (damageVariance ~/ 2))
            .clamp(1, 999999);

        final enemyDefense = (enemy['defense'] as int?) ?? 2;
        final damageTaken = (playerDamage - enemyDefense).clamp(1, playerDamage);

        final playerCritChance = _gameService.playerState.critRate;
        final isCritical = _random.nextDouble() < playerCritChance;
        final finalDamage =
            isCritical ? (damageTaken * 1.5).round() : damageTaken;

        enemy['hp'] = (enemy['hp'] as int) - finalDamage;
        totalDamageDealt += finalDamage;

        if (isCritical) {
          combatLog.add(
              'CRITICAL: You strike ${enemy['name']} for $finalDamage damage!');
        } else {
          combatLog.add('You strike ${enemy['name']} for $finalDamage damage.');
        }

        if ((enemy['hp'] as int) <= 0) {
          combatLog.add('${enemy['name']} has been defeated!');
          monstersDefeated++;
        }
      }

      // Remove defeated enemies
      enemyCopies.removeWhere((e) => (e['hp'] as int) <= 0);

      if (enemyCopies.isEmpty) break;

      // Enemies attack player
      int roundDamage = 0;
      for (final enemy in enemyCopies) {
        final enemyDamage = (enemy['damage'] as int?) ?? 3;
        roundDamage += enemyDamage;
      }

      final playerDefense = _gameService.playerState.baseDefense;
      final mitigatedDamage = (roundDamage - (playerDefense ~/ 2)).clamp(1, roundDamage);
      totalDamageTaken += mitigatedDamage;

      combatLog.add('Enemies deal $mitigatedDamage damage to you.');

      applyDamageToPlayer(mitigatedDamage);

      if (_gameService.playerState.hp <= 0) {
        combatLog.add('You have been defeated!');
        return CombatResult(
          victory: false,
          combatLog: combatLog,
          damageDealt: totalDamageDealt,
          damageTaken: totalDamageTaken,
          rewardsEarned: {},
          monstersDefeated: monstersDefeated,
        );
      }
    }

    final rewards = _calculateEncounterRewards(context, monstersDefeated);
    awardRewards(rewards);

    return CombatResult(
      victory: true,
      combatLog: combatLog,
      damageDealt: totalDamageDealt,
      damageTaken: totalDamageTaken,
      rewardsEarned: rewards,
      monstersDefeated: monstersDefeated,
    );
  }

  void applyDamageToPlayer(int damage) {
    final defense = _gameService.playerState.baseDefense;
    final mitigatedDamage = (damage - (defense ~/ 2)).clamp(1, damage);
    final newHp =
        (_gameService.playerState.hp - mitigatedDamage).clamp(0, _gameService.playerState.maxHp);
    _gameService.updateHp(newHp);
  }

  void awardRewards(Map<String, int> rewards) {
    var playerState = _gameService.playerState;

    if (rewards.containsKey('moonlight')) {
      _gameService.addMoonlight(rewards['moonlight']!);
    }

    final otherRewards = Map<String, int>.from(rewards);
    otherRewards.remove('moonlight');

    if (otherRewards.isNotEmpty) {
      final newResources = Map<String, int>.from(playerState.resources);
      otherRewards.forEach((key, value) {
        newResources[key] = (newResources[key] ?? 0) + value;
      });
      _gameService.updatePlayerState(
        playerState.copyWith(resources: newResources),
      );
    }
  }
}
