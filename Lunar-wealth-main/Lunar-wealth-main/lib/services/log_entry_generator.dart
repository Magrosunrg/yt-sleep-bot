import 'dart:math';
import '../models/log_entry.dart';
import '../models/choice_option.dart';
import '../models/encounter_context.dart';

class LogEntryGenerator {
  final Random _random = Random();

  ExplorationLogEntry generateLogEntry(
    int elapsedTimeSeconds,
    int difficultyLevel, {
    bool allowChoices = false,
  }) {
    final eventType = _selectEventType(elapsedTimeSeconds, allowChoices);
    final timestamp = DateTime.now();
    final id = '${timestamp.millisecondsSinceEpoch}_${_random.nextInt(1000)}';

    switch (eventType) {
      case LogEntryType.discovery:
        return allowChoices
            ? _generateDiscovery(
                id, timestamp, elapsedTimeSeconds, difficultyLevel)
            : _generateNarrativeDiscovery(
                id, timestamp, elapsedTimeSeconds, difficultyLevel);
      case LogEntryType.encounter:
        return allowChoices
            ? _generateEncounter(
                id, timestamp, elapsedTimeSeconds, difficultyLevel)
            : _generateNarrativeEncounter(
                id, timestamp, elapsedTimeSeconds, difficultyLevel);
      case LogEntryType.reward:
        return allowChoices
            ? _generateReward(
                id, timestamp, elapsedTimeSeconds, difficultyLevel)
            : _generateNarrativeReward(
                id, timestamp, elapsedTimeSeconds, difficultyLevel);
      case LogEntryType.challenge:
        return allowChoices
            ? _generateChallenge(
                id, timestamp, elapsedTimeSeconds, difficultyLevel)
            : _generateNarrativeChallenge(
                id, timestamp, elapsedTimeSeconds, difficultyLevel);
      case LogEntryType.exploration:
        return _generateExploration(
            id, timestamp, elapsedTimeSeconds, difficultyLevel, allowChoices);
    }
  }

  LogEntryType _selectEventType(int elapsedTimeSeconds, bool allowChoices) {
    final minutes = elapsedTimeSeconds / 60.0;
    final weights = _getEventWeights(minutes, allowChoices);
    final totalWeight = weights.values.reduce((a, b) => a + b);
    final roll = _random.nextDouble() * totalWeight;

    double cumulative = 0;
    for (final entry in weights.entries) {
      cumulative += entry.value;
      if (roll <= cumulative) {
        return entry.key;
      }
    }

    return LogEntryType.exploration;
  }

  Map<LogEntryType, double> _getEventWeights(double minutes, bool allowChoices) {
    if (!allowChoices) {
      return {
        LogEntryType.exploration: 50.0,
        LogEntryType.discovery: 20.0,
        LogEntryType.encounter: 15.0,
        LogEntryType.reward: 10.0,
        LogEntryType.challenge: 5.0,
      };
    }

    if (minutes < 1) {
      return {
        LogEntryType.discovery: 30.0,
        LogEntryType.exploration: 40.0,
        LogEntryType.reward: 20.0,
        LogEntryType.encounter: 5.0,
        LogEntryType.challenge: 5.0,
      };
    } else if (minutes < 3) {
      return {
        LogEntryType.discovery: 25.0,
        LogEntryType.exploration: 30.0,
        LogEntryType.reward: 20.0,
        LogEntryType.encounter: 15.0,
        LogEntryType.challenge: 10.0,
      };
    } else if (minutes < 5) {
      return {
        LogEntryType.discovery: 20.0,
        LogEntryType.exploration: 20.0,
        LogEntryType.reward: 20.0,
        LogEntryType.encounter: 25.0,
        LogEntryType.challenge: 15.0,
      };
    } else {
      return {
        LogEntryType.discovery: 15.0,
        LogEntryType.exploration: 15.0,
        LogEntryType.reward: 15.0,
        LogEntryType.encounter: 30.0,
        LogEntryType.challenge: 25.0,
      };
    }
  }

  ExplorationLogEntry _generateDiscovery(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final buildingChance = (difficultyLevel * 2).clamp(5, 40) / 100.0;
    final isBuilding = _random.nextDouble() < buildingChance;

    if (isBuilding) {
      return _generateBuildingDiscovery(
        id,
        timestamp,
        elapsedTimeSeconds,
        difficultyLevel,
      );
    }

    final discoveries = [
      {
        'title': 'Abandoned Cottage',
        'desc':
            'You entered a small cottage. Dust covers everything, but moonlight streams through the windows.',
      },
      {
        'title': 'Empty Barn',
        'desc':
            'A weathered barn stands open. Inside, you find remnants of old tools and a faint glow.',
      },
      {
        'title': 'Crumbling Tower',
        'desc':
            'You climb the stairs of an ancient tower. At the top, moonlight pools in a forgotten chamber.',
      },
      {
        'title': 'Mysterious Shrine',
        'desc':
            'A small shrine dedicated to the moon. Offerings left here have turned to moonlight.',
      },
      {
        'title': 'Hidden Cellar',
        'desc':
            'You discover a cellar beneath an old foundation. Jars filled with crystallized moonlight line the shelves.',
      },
    ];

    final discovery = discoveries[_random.nextInt(discoveries.length)];
    final baseReward = 10 + (difficultyLevel * 5);
    final moonlightReward = baseReward + _random.nextInt(5);

    final choices = [
      ChoiceOption(
        id: 'explore',
        label: 'Explore Further',
        description: 'Search for hidden treasures',
        consequences: {'moonlight': (moonlightReward * 1.2).round()},
      ),
      ChoiceOption(
        id: 'leave',
        label: 'Leave',
        description: 'Move on to other locations',
        consequences: {'moonlight': moonlightReward},
      ),
    ];

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.discovery,
      logLevel: LogLevel.event,
      title: discovery['title'] as String,
      description: discovery['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: {'moonlight': moonlightReward},
      choices: choices,
    );
  }

  ExplorationLogEntry _generateBuildingDiscovery(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final buildings = [
      {
        'title': 'Ancient Tower',
        'desc':
            'An imposing stone tower rises before you, covered in lunar runes. You sense treasure within.',
        'type': 'tower',
      },
      {
        'title': 'Lunar Archive',
        'desc':
            'A vast library of moonlit knowledge awaits. Ancient texts glow with ethereal light.',
        'type': 'archive',
      },
      {
        'title': 'Forgotten Ruins',
        'desc':
            'Crumbling stone structures hint at an ancient civilization. Moonlight dances across the stones.',
        'type': 'ruins',
      },
      {
        'title': 'Moonlit Shrine',
        'desc':
            'A sacred shrine emanates divine lunar energy. Blessings might await the worthy.',
        'type': 'shrine',
      },
      {
        'title': 'Lunar Vault',
        'desc':
            'A fortified vault sealed with ancient magic. Great treasures lie hidden within.',
        'type': 'vault',
      },
    ];

    final building = buildings[_random.nextInt(buildings.length)];
    final baseReward = 15 + (difficultyLevel * 7);

    final buildingType = building['type'] as String;
    final buildingTitle = building['title'] as String;

    final choices = [
      ChoiceOption(
        id: 'enter_building',
        label: 'Enter',
        description: 'Explore the building',
        consequences: {
          'requires_building': 1,
          'building_type': buildingType.hashCode
        },
      ),
      ChoiceOption(
        id: 'skip_building',
        label: 'Skip',
        description: 'Leave it for later',
        consequences: {'moonlight': baseReward},
      ),
    ];

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.discovery,
      logLevel: LogLevel.event,
      title: buildingTitle,
      description: building['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: {'moonlight': baseReward},
      choices: choices,
      eventData: {'building_type': buildingType},
    );
  }

  ExplorationLogEntry _generateEncounter(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final encounters = [
      {
        'title': 'Wandering Spirit',
        'desc':
            'A ghostly figure passes through you. It leaves behind traces of moonlight.'
      },
      {
        'title': 'Lunar Fox',
        'desc':
            'A fox made of moonlight bounds past, dropping glowing essence in its wake.'
      },
      {
        'title': 'Shadow Beast',
        'desc': 'A shadow creature appears before you.'
      },
      {
        'title': 'Ancient Guardian',
        'desc': 'A stone guardian awakens briefly, assessing your worthiness.'
      },
    ];

    final encounter = encounters[_random.nextInt(encounters.length)];
    final baseMoonlight = 15 + (difficultyLevel * 8);

    final minEnemies = (difficultyLevel / 5).ceil();
    final maxEnemies = minEnemies + 2;

    final multiEnemyChance = (difficultyLevel * 5).clamp(0, 70) / 100.0;
    final isSolo = _random.nextDouble() > multiEnemyChance;

    final encounterContext = EncounterContext(
      id: '$id-encounter',
      difficultyLevel: difficultyLevel,
      minEnemies: minEnemies,
      maxEnemies: maxEnemies,
      resourceScaling: {'shadow_essence': 100 + (difficultyLevel * 10)},
      isSoloEncounter: isSolo,
      elapsedTimeSeconds: elapsedTimeSeconds,
    );

    final choices = [
      ChoiceOption(
        id: 'fight',
        label: 'Fight',
        description: 'Engage in combat',
        consequences: {'moonlight': baseMoonlight, 'requires_combat': 1},
      ),
      ChoiceOption(
        id: 'flee',
        label: 'Flee',
        description: 'Attempt to escape',
        consequences: {'moonlight': (baseMoonlight * 0.3).round()},
      ),
    ];

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.encounter,
      logLevel: LogLevel.encounter,
      title: encounter['title'] as String,
      description: encounter['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: {'moonlight': baseMoonlight},
      choices: choices,
      encounterContext: encounterContext,
    );
  }

  ExplorationLogEntry _generateReward(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final rewards = [
      {
        'title': 'Moonstone Fragment',
        'desc': 'You find a fragment of pure moonstone buried in the earth.'
      },
      {
        'title': 'Lunar Crystals',
        'desc': 'A cluster of crystals catches the moonlight and amplifies it.'
      },
      {
        'title': 'Ancient Coin',
        'desc': 'A silver coin engraved with lunar runes. It radiates power.'
      },
      {
        'title': 'Starfall Gem',
        'desc':
            'A gem that fell from the sky, containing concentrated moonlight.'
      },
    ];

    final reward = rewards[_random.nextInt(rewards.length)];
    final baseReward = 20 + (difficultyLevel * 10);

    final choices = [
      ChoiceOption(
        id: 'take',
        label: 'Take It',
        description: 'Claim the reward',
        consequences: {'moonlight': baseReward},
      ),
      const ChoiceOption(
        id: 'leave_reward',
        label: 'Leave It',
        description: 'Leave it for others',
        consequences: {},
      ),
    ];

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.reward,
      logLevel: LogLevel.loot,
      title: reward['title'] as String,
      description: reward['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: {'moonlight': baseReward},
      choices: choices,
    );
  }

  ExplorationLogEntry _generateChallenge(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final challenges = [
      {
        'title': 'Moonlight Puzzle',
        'desc': 'You solve an ancient puzzle carved into stone.'
      },
      {
        'title': 'Midnight Trial',
        'desc':
            'You face a trial of courage and wit. Success brings great reward.'
      },
      {
        'title': 'Shadow Gauntlet',
        'desc':
            'You navigate through twisting shadows to reach a moonlight cache.'
      },
      {
        'title': 'Lunar Riddle',
        'desc':
            'An ancient voice poses a riddle. Your correct answer is rewarded.'
      },
    ];

    final challenge = challenges[_random.nextInt(challenges.length)];
    final baseReward = 25 + (difficultyLevel * 12);

    final choices = [
      ChoiceOption(
        id: 'attempt',
        label: 'Attempt',
        description: 'Try to overcome the challenge',
        consequences: {'moonlight': baseReward},
      ),
      ChoiceOption(
        id: 'skip',
        label: 'Skip',
        description: 'Avoid the challenge',
        consequences: {'moonlight': (baseReward * 0.2).round()},
      ),
    ];

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.challenge,
      logLevel: LogLevel.warning,
      title: challenge['title'] as String,
      description: challenge['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: {'moonlight': baseReward},
      choices: choices,
    );
  }

  ExplorationLogEntry _generateExploration(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
    bool allowChoices,
  ) {
    final explorations = [
      {
        'title': 'Moonlit Meadow',
        'desc': 'You rest in a peaceful meadow bathed in moonlight.'
      },
      {
        'title': 'Quiet Grove',
        'desc':
            'The trees whisper ancient secrets as moonlight filters through leaves.'
      },
      {
        'title': 'Serene Pool',
        'desc':
            'A still pool reflects the moon perfectly, and you collect the reflection.'
      },
      {
        'title': 'Starlit Path',
        'desc': 'You walk a path illuminated by stars and moon alike.'
      },
    ];

    final exploration = explorations[_random.nextInt(explorations.length)];

    if (!allowChoices) {
      // Only 8% chance of rewards for narrative exploration entries
      final hasRewards = _random.nextDouble() < 0.08;
      final rewards = hasRewards 
          ? {'moonlight': 5 + (difficultyLevel * 2)}
          : <String, int>{};
      
      return ExplorationLogEntry(
        id: id,
        type: LogEntryType.exploration,
        logLevel: LogLevel.info,
        title: exploration['title'] as String,
        description: exploration['desc'] as String,
        timestamp: timestamp,
        difficultyLevel: difficultyLevel,
        elapsedTimeSeconds: elapsedTimeSeconds,
        rewards: rewards,
        choices: [],
      );
    }

    final baseReward = 5 + (difficultyLevel * 2);

    final choices = [
      ChoiceOption(
        id: 'continue',
        label: 'Continue Exploring',
        description: 'Keep moving forward',
        consequences: {'moonlight': baseReward},
      ),
      const ChoiceOption(
        id: 'rest',
        label: 'Rest',
        description: 'Take a moment to recover',
        consequences: {'hp_restore': 10},
      ),
    ];

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.exploration,
      logLevel: LogLevel.info,
      title: exploration['title'] as String,
      description: exploration['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: {'moonlight': baseReward},
      choices: choices,
    );
  }

  ExplorationLogEntry _generateNarrativeDiscovery(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final discoveries = [
      {
        'title': 'Abandoned Cottage',
        'desc':
            'You entered a small cottage. Dust covers everything, but moonlight streams through the windows.',
      },
      {
        'title': 'Empty Barn',
        'desc':
            'A weathered barn stands open. Inside, you find remnants of old tools and a faint glow.',
      },
      {
        'title': 'Crumbling Tower',
        'desc':
            'You climb the stairs of an ancient tower. At the top, moonlight pools in a forgotten chamber.',
      },
      {
        'title': 'Mysterious Shrine',
        'desc':
            'A small shrine dedicated to the moon. Offerings left here have turned to moonlight.',
      },
      {
        'title': 'Hidden Cellar',
        'desc':
            'You discover a cellar beneath an old foundation. Jars filled with crystallized moonlight line the shelves.',
      },
    ];

    final discovery = discoveries[_random.nextInt(discoveries.length)];
    
    // Only 15% chance of rewards for narrative discovery entries
    final hasRewards = _random.nextDouble() < 0.15;
    final rewards = hasRewards 
        ? {'moonlight': 10 + (difficultyLevel * 5) + _random.nextInt(5)}
        : <String, int>{};

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.discovery,
      logLevel: LogLevel.event,
      title: discovery['title'] as String,
      description: discovery['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: rewards,
      choices: [],
    );
  }

  ExplorationLogEntry _generateNarrativeEncounter(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final encounters = [
      {
        'title': 'Wandering Spirit',
        'desc':
            'A ghostly figure passes through you. It leaves behind traces of moonlight.'
      },
      {
        'title': 'Lunar Fox',
        'desc':
            'A fox made of moonlight bounds past, dropping glowing essence in its wake.'
      },
      {
        'title': 'Shadow Beast',
        'desc': 'A shadow creature appears before you, watching curiously.'
      },
      {
        'title': 'Ancient Guardian',
        'desc':
            'A stone guardian seems to acknowledge your presence with an ancient nod.'
      },
    ];

    final encounter = encounters[_random.nextInt(encounters.length)];
    
    // Only 10% chance of rewards for narrative encounter entries
    final hasRewards = _random.nextDouble() < 0.10;
    final rewards = hasRewards 
        ? {'moonlight': 15 + (difficultyLevel * 8)}
        : <String, int>{};

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.encounter,
      logLevel: LogLevel.encounter,
      title: encounter['title'] as String,
      description: encounter['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: rewards,
      choices: [],
    );
  }

  ExplorationLogEntry _generateNarrativeReward(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final rewards = [
      {
        'title': 'Moonstone Fragment',
        'desc': 'You find a fragment of pure moonstone buried in the earth.'
      },
      {
        'title': 'Lunar Crystals',
        'desc': 'A cluster of crystals catches the moonlight and amplifies it.'
      },
      {
        'title': 'Ancient Coin',
        'desc': 'A silver coin engraved with lunar runes. It radiates power.'
      },
      {
        'title': 'Starfall Gem',
        'desc':
            'A gem that fell from the sky, containing concentrated moonlight.'
      },
    ];

    final reward = rewards[_random.nextInt(rewards.length)];
    
    // Only 20% chance of actual rewards for narrative reward entries
    final hasRewards = _random.nextDouble() < 0.20;
    final rewardAmount = hasRewards 
        ? 20 + (difficultyLevel * 10)
        : 0;
    final rewardsMap = rewardAmount > 0 
        ? {'moonlight': rewardAmount}
        : <String, int>{};

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.reward,
      logLevel: LogLevel.loot,
      title: reward['title'] as String,
      description: reward['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: rewardsMap,
      choices: [],
    );
  }

  ExplorationLogEntry _generateNarrativeChallenge(
    String id,
    DateTime timestamp,
    int elapsedTimeSeconds,
    int difficultyLevel,
  ) {
    final challenges = [
      {
        'title': 'Moonlight Puzzle',
        'desc': 'You solve an ancient puzzle carved into stone.'
      },
      {
        'title': 'Midnight Trial',
        'desc':
            'You face a trial of courage and wit. Success brings great reward.'
      },
      {
        'title': 'Shadow Gauntlet',
        'desc':
            'You navigate through twisting shadows to reach a moonlight cache.'
      },
      {
        'title': 'Lunar Riddle',
        'desc':
            'An ancient voice poses a riddle. Your answer is rewarded with power.'
      },
    ];

    final challenge = challenges[_random.nextInt(challenges.length)];
    
    // Only 12% chance of rewards for narrative challenge entries
    final hasRewards = _random.nextDouble() < 0.12;
    final rewards = hasRewards 
        ? {'moonlight': 25 + (difficultyLevel * 12)}
        : <String, int>{};

    return ExplorationLogEntry(
      id: id,
      type: LogEntryType.challenge,
      logLevel: LogLevel.warning,
      title: challenge['title'] as String,
      description: challenge['desc'] as String,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
      elapsedTimeSeconds: elapsedTimeSeconds,
      rewards: rewards,
      choices: [],
    );
  }
}
