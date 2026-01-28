import 'dart:math';
import '../models/exploration_event.dart';

class EventGenerator {
  final Random _random = Random();

  ExplorationEvent generateEvent(int totalExplorationTimeSeconds, int difficultyLevel) {
    final eventType = _selectEventType(totalExplorationTimeSeconds);
    final timestamp = DateTime.now();
    final id = '${timestamp.millisecondsSinceEpoch}_${_random.nextInt(1000)}';

    switch (eventType) {
      case EventType.buildingDiscovery:
        return _generateBuildingDiscovery(id, timestamp, totalExplorationTimeSeconds, difficultyLevel);
      case EventType.encounter:
        return _generateEncounter(id, timestamp, totalExplorationTimeSeconds, difficultyLevel);
      case EventType.treasure:
        return _generateTreasure(id, timestamp, totalExplorationTimeSeconds, difficultyLevel);
      case EventType.challenge:
        return _generateChallenge(id, timestamp, totalExplorationTimeSeconds, difficultyLevel);
      case EventType.peaceful:
        return _generatePeaceful(id, timestamp, totalExplorationTimeSeconds, difficultyLevel);
    }
  }

  EventType _selectEventType(int totalExplorationTimeSeconds) {
    final weights = _getEventWeights(totalExplorationTimeSeconds);
    final totalWeight = weights.values.reduce((a, b) => a + b);
    final roll = _random.nextDouble() * totalWeight;

    double cumulative = 0;
    for (final entry in weights.entries) {
      cumulative += entry.value;
      if (roll <= cumulative) {
        return entry.key;
      }
    }

    return EventType.peaceful;
  }

  Map<EventType, double> _getEventWeights(int totalExplorationTimeSeconds) {
    final minutes = totalExplorationTimeSeconds / 60.0;

    if (minutes < 1) {
      return {
        EventType.buildingDiscovery: 30.0,
        EventType.peaceful: 40.0,
        EventType.treasure: 20.0,
        EventType.encounter: 5.0,
        EventType.challenge: 5.0,
      };
    } else if (minutes < 3) {
      return {
        EventType.buildingDiscovery: 25.0,
        EventType.peaceful: 30.0,
        EventType.treasure: 20.0,
        EventType.encounter: 15.0,
        EventType.challenge: 10.0,
      };
    } else if (minutes < 5) {
      return {
        EventType.buildingDiscovery: 20.0,
        EventType.peaceful: 20.0,
        EventType.treasure: 20.0,
        EventType.encounter: 25.0,
        EventType.challenge: 15.0,
      };
    } else {
      return {
        EventType.buildingDiscovery: 15.0,
        EventType.peaceful: 15.0,
        EventType.treasure: 15.0,
        EventType.encounter: 30.0,
        EventType.challenge: 25.0,
      };
    }
  }

  ExplorationEvent _generateBuildingDiscovery(
    String id,
    DateTime timestamp,
    int totalExplorationTimeSeconds,
    int difficultyLevel,
  ) {
    final outcomes = [
      {'title': 'Abandoned Cottage', 'desc': 'You entered a small cottage. Dust covers everything, but moonlight streams through the windows.', 'moonlight': 5},
      {'title': 'Empty Barn', 'desc': 'A weathered barn stands open. Inside, you find remnants of old tools and a faint glow.', 'moonlight': 8},
      {'title': 'Crumbling Tower', 'desc': 'You climb the stairs of an ancient tower. At the top, moonlight pools in a forgotten chamber.', 'moonlight': 12},
      {'title': 'Mysterious Shrine', 'desc': 'A small shrine dedicated to the moon. Offerings left here have turned to moonlight.', 'moonlight': 15},
      {'title': 'Hidden Cellar', 'desc': 'You discover a cellar beneath an old foundation. Jars filled with crystallized moonlight line the shelves.', 'moonlight': 20},
      {'title': 'Abandoned Workshop', 'desc': 'The workshop is empty, but the forge still glows faintly with lunar energy.', 'moonlight': 10},
      {'title': 'Old Library', 'desc': 'Books scatter the floor. One tome pulses with captured moonlight between its pages.', 'moonlight': 18},
    ];

    final outcome = outcomes[_random.nextInt(outcomes.length)];
    final moonlightMultiplier = 1.0 + (difficultyLevel * 0.1);
    final moonlight = ((outcome['moonlight'] as int) * moonlightMultiplier).round();

    return ExplorationEvent(
      id: id,
      type: EventType.buildingDiscovery,
      title: outcome['title'] as String,
      description: outcome['desc'] as String,
      moonlightReward: moonlight,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
    );
  }

  ExplorationEvent _generateEncounter(
    String id,
    DateTime timestamp,
    int totalExplorationTimeSeconds,
    int difficultyLevel,
  ) {
    final encounters = [
      {'title': 'Wandering Spirit', 'desc': 'A ghostly figure passes through you. It leaves behind traces of moonlight.', 'moonlight': 12},
      {'title': 'Lunar Fox', 'desc': 'A fox made of moonlight bounds past, dropping glowing essence in its wake.', 'moonlight': 15},
      {'title': 'Lost Traveler', 'desc': 'You meet a lost traveler who offers you moonlight in exchange for directions.', 'moonlight': 18},
      {'title': 'Shadow Beast', 'desc': 'A shadow creature challenges you but retreats, leaving moonlight behind.', 'moonlight': 22},
      {'title': 'Moon Sprite', 'desc': 'A tiny sprite of pure moonlight dances around you, gifting you with energy.', 'moonlight': 25},
      {'title': 'Ancient Guardian', 'desc': 'A stone guardian awakens briefly, nods in acknowledgment, and grants you moonlight.', 'moonlight': 30},
      {'title': 'Celestial Wolf', 'desc': 'A magnificent wolf howls at the moon, and moonlight rains down around you.', 'moonlight': 35},
    ];

    final encounter = encounters[_random.nextInt(encounters.length)];
    final moonlightMultiplier = 1.0 + (difficultyLevel * 0.15);
    final moonlight = ((encounter['moonlight'] as int) * moonlightMultiplier).round();

    return ExplorationEvent(
      id: id,
      type: EventType.encounter,
      title: encounter['title'] as String,
      description: encounter['desc'] as String,
      moonlightReward: moonlight,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
    );
  }

  ExplorationEvent _generateTreasure(
    String id,
    DateTime timestamp,
    int totalExplorationTimeSeconds,
    int difficultyLevel,
  ) {
    final treasures = [
      {'title': 'Moonstone Fragment', 'desc': 'You find a fragment of pure moonstone buried in the earth.', 'moonlight': 25},
      {'title': 'Lunar Crystals', 'desc': 'A cluster of crystals catches the moonlight and amplifies it.', 'moonlight': 30},
      {'title': 'Ancient Coin', 'desc': 'A silver coin engraved with lunar runes. It radiates power.', 'moonlight': 35},
      {'title': 'Starfall Gem', 'desc': 'A gem that fell from the sky, containing concentrated moonlight.', 'moonlight': 40},
      {'title': 'Moon Vessel', 'desc': 'An ornate vessel filled with liquid moonlight that never spills.', 'moonlight': 50},
      {'title': 'Celestial Artifact', 'desc': 'An artifact of unknown origin pulses with lunar energy.', 'moonlight': 60},
    ];

    final minutes = totalExplorationTimeSeconds / 60.0;
    final availableTreasures = treasures.where((t) {
      final value = t['moonlight'] as int;
      if (minutes < 2) return value <= 30;
      if (minutes < 4) return value <= 40;
      return true;
    }).toList();

    final treasure = availableTreasures.isNotEmpty
        ? availableTreasures[_random.nextInt(availableTreasures.length)]
        : treasures[0];

    final moonlightMultiplier = 1.0 + (difficultyLevel * 0.12);
    final moonlight = ((treasure['moonlight'] as int) * moonlightMultiplier).round();

    return ExplorationEvent(
      id: id,
      type: EventType.treasure,
      title: treasure['title'] as String,
      description: treasure['desc'] as String,
      moonlightReward: moonlight,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
    );
  }

  ExplorationEvent _generateChallenge(
    String id,
    DateTime timestamp,
    int totalExplorationTimeSeconds,
    int difficultyLevel,
  ) {
    final challenges = [
      {'title': 'Moonlight Puzzle', 'desc': 'You solve an ancient puzzle carved into stone. Moonlight pours from the solution.', 'moonlight': 28},
      {'title': 'Midnight Trial', 'desc': 'You face a trial of courage and wit. Success brings great reward.', 'moonlight': 35},
      {'title': 'Shadow Gauntlet', 'desc': 'You navigate through twisting shadows to reach a moonlight cache.', 'moonlight': 42},
      {'title': 'Lunar Riddle', 'desc': 'An ancient voice poses a riddle. Your correct answer is rewarded.', 'moonlight': 38},
      {'title': 'Test of Will', 'desc': 'You resist a powerful illusion and claim the moonlight it was guarding.', 'moonlight': 45},
      {'title': 'Moongate Challenge', 'desc': 'You pass through a dangerous moongate and emerge with precious energy.', 'moonlight': 55},
    ];

    final challenge = challenges[_random.nextInt(challenges.length)];
    final moonlightMultiplier = 1.0 + (difficultyLevel * 0.18);
    final moonlight = ((challenge['moonlight'] as int) * moonlightMultiplier).round();

    return ExplorationEvent(
      id: id,
      type: EventType.challenge,
      title: challenge['title'] as String,
      description: challenge['desc'] as String,
      moonlightReward: moonlight,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
    );
  }

  ExplorationEvent _generatePeaceful(
    String id,
    DateTime timestamp,
    int totalExplorationTimeSeconds,
    int difficultyLevel,
  ) {
    final peaceful = [
      {'title': 'Moonlit Meadow', 'desc': 'You rest in a peaceful meadow bathed in moonlight.', 'moonlight': 5},
      {'title': 'Quiet Grove', 'desc': 'The trees whisper ancient secrets as moonlight filters through leaves.', 'moonlight': 7},
      {'title': 'Serene Pool', 'desc': 'A still pool reflects the moon perfectly, and you collect the reflection.', 'moonlight': 10},
      {'title': 'Starlit Path', 'desc': 'You walk a path illuminated by stars and moon alike.', 'moonlight': 8},
      {'title': 'Gentle Breeze', 'desc': 'A breeze carries moonlight dust that settles around you.', 'moonlight': 6},
      {'title': 'Lunar Bloom', 'desc': 'Flowers that only bloom under the moon release moonlight pollen.', 'moonlight': 12},
    ];

    final event = peaceful[_random.nextInt(peaceful.length)];
    final moonlightMultiplier = 1.0 + (difficultyLevel * 0.08);
    final moonlight = ((event['moonlight'] as int) * moonlightMultiplier).round();

    return ExplorationEvent(
      id: id,
      type: EventType.peaceful,
      title: event['title'] as String,
      description: event['desc'] as String,
      moonlightReward: moonlight,
      timestamp: timestamp,
      difficultyLevel: difficultyLevel,
    );
  }
}
