# Lunar Shell

A Candy Box-inspired text adventure game built with Flutter.

## Features

- **Portrait-only mode**: The app is locked to portrait orientation for optimal mobile gameplay
- **Persistent storage**: Player progress is saved using SharedPreferences
- **ASCII aesthetic**: Monospaced fonts and ASCII art create a retro terminal feel
- **Lunar theme**: Dark color palette inspired by moonlit nights
- **Exploration Log System**: Timed exploration with procedurally generated log entries and progressive difficulty
- **Log-based Encounters**: Branching choices with consequences that affect player resources and state
- **Multi-resource Economy**: Moonlight collection plus diverse resource types for equipment progression
- **Combat Resolution**: Inline combat resolution with damage calculations and reward distribution

## Architecture

### Core Services

- **StorageService**: JSON persistence layer using SharedPreferences
- **LunarGameService**: ChangeNotifier that manages player state, moonlight, and multi-resource economy
- **InventoryService**: Manages player inventory and equipment upgrades (weapon/armor tiers)
- **ExplorationService**: Original exploration session manager (legacy, kept for compatibility)
- **ExplorationLogService**: New log-first exploration engine that emits log entries with branching choices
- **LogEntryGenerator**: Generates diverse exploration log entries based on elapsed time and difficulty
- **CombatService**: Handles encounter resolution with damage calculations and reward scaling

### Models

- **PlayerState**: Immutable state model for player data (HP, Moonlight, Equipment, Resources, Build Run flag)
- **ExplorationLogEntry**: Represents individual log entries with type, title, description, choices, and consequences
- **ChoiceOption**: Represents branching choices available to the player for each log entry
- **EncounterContext**: Context information for encounters including difficulty, enemy count range, and resource scaling
- **ExplorationState**: Immutable state model for exploration sessions (legacy, kept for compatibility)
- **ExplorationEvent**: Event model (legacy, kept for compatibility)

### Screens

- **MainMenuScreen**: Entry point with game title and explore button
- **ExploreScreen**: Main gameplay screen with exploration mechanics
- **HomeScreen**: Player hub displaying current stats and resources

## Dependencies

This project uses minimal dependencies:
- Flutter SDK
- provider (^6.1.1) - State management
- shared_preferences (^2.2.2) - Local storage

## Getting Started

```bash
# Get dependencies
flutter pub get

# Run the app
flutter run

# Run tests
flutter test

# Analyze code
flutter analyze
```

## Game Mechanics

### Exploration Log System

The core gameplay loop is built around the exploration log engine:

1. **Log Entry Generation**: At regular intervals (3-8 seconds, shorter at higher difficulty), the system generates new log entries
2. **Entry Types**: Exploration, Discovery, Encounter, Reward, Challenge
3. **Branching Choices**: Each log entry presents 1-2 choices with different consequences
4. **Difficulty Scaling**: Difficulty increases every 120 seconds of exploration, affecting:
   - Entry variation and intensity
   - NPC behavior and rewards
   - Combat difficulty if encounters occur

### Resource Economy

**Primary Resource: Moonlight**
- Earned from all exploration activities
- Used for equipment upgrades
- Converted to other resources in trading scenarios

**Secondary Resources:**
- Shadow Essence: Combat drops, used for weapon upgrades
- Lunar Claw: Boss/elite drops, rare resource for advanced upgrades
- Moon Essence: Treasure finds, supports armor/accessory upgrades
- Moon Crystal: Late-game resources from challenging encounters

### Combat System

- **Inline Solo Encounters**: Single enemies resolved immediately with damage calculations
- **Multi-Enemy Encounters**: Groups of 1-3 enemies (scales with difficulty)
- **Damage Calculation**: Player damage = base + random variance, mitigated by enemy defense
- **Critical Strikes**: Calculated from player crit rate, deal 1.5x damage
- **Player Defense**: Reduces incoming damage by defense/2
- **Encounter Rewards**: Scaled based on difficulty level and number of enemies defeated

### Persistence

All exploration progress, player state, and log history persist across app restarts:
- Log history stored in SharedPreferences (limited to recent 100 entries)
- Player resources and equipment state saved
- Exploration session state preserved (can resume exploration)

## Legacy Systems

The following older systems remain for backward compatibility but are superseded by the new log system:
- **ExplorationService**: Original event-based exploration (replaced by ExplorationLogService)
- **EventGenerator**: Original event generation (replaced by LogEntryGenerator)
- **ExplorationEvent**: Original event model (replaced by ExplorationLogEntry)

New development should use the ExplorationLogService and related models for all exploration features.
