# Exploration System

## Overview
The exploration system allows players to discover and travel between different locations in the Lunar Shell world. Each location has unique characteristics, enemy pools, and unlock requirements.

## Architecture

### Data Layer
- **`lib/data/locations.dart`**: Static location definitions with:
  - Location metadata (ID, name, flavor text)
  - ASCII minimaps
  - Enemy spawn pools with weights
  - Unlock requirements
  - Story beat hooks

### Models
- **`lib/models/location.dart`**: Location and UnlockRequirement data structures
- **`lib/models/world_state.dart`**: Persistent world state including:
  - Current location
  - Visit counts per location
  - Travel cooldowns
  - Unlocked locations
  - Viewed story beats

### Services
- **`lib/services/world_service.dart`**: Core world management service that:
  - Manages current location and travel
  - Handles location unlocking
  - Generates encounters based on location spawn pools
  - Tracks exploration counts
  - Persists state via StorageService

### UI
- **`lib/screens/exploration_screen.dart`**: Main exploration interface featuring:
  - Current location display with ASCII map
  - Location flavor text and metadata
  - Hunt for prey action (generates encounters)
  - Location list with travel functionality
  - Available locations to unlock
  - Story beat presentation

## Locations

### Moonlit Clearing
- **ID**: `moonlit_clearing`
- **Unlock**: Available from start
- **Enemies**: Shadow Wolf (100%)
- **Story**: Your journey begins here, beneath the eternal moon

### Silver Pines
- **ID**: `silver_pines`
- **Unlock**: Defeat 5 Shadow Wolves
- **Enemies**: Shadow Wolf (60%), Moon Wolf (40%)
- **Story**: Ancient pines with bark that shimmers like moonlit metal

### Crater Rim
- **ID**: `crater_rim`
- **Unlock**: Collect 100 moonlight + unlock Silver Pines
- **Enemies**: Shadow Wolf (30%), Moon Wolf (70%)
- **Story**: The edge of a massive impact crater with strange crystals

## Gameplay Flow

1. **Starting Out**: Players begin at Moonlit Clearing
2. **Exploration**: Click "Hunt for Prey" to generate an encounter from the location's enemy pool
3. **Combat**: Encounters launch combat with location-specific enemies
4. **Progress**: Defeat enemies and collect moonlight to unlock new areas
5. **Travel**: Move between unlocked locations (3-second cooldown)
6. **Discovery**: View story beats when visiting locations for the first time

## Persistence

All world state persists through `StorageService`:
- Current location survives app restarts
- Unlocked locations are remembered
- Visit counts accumulate across sessions
- Story beat views are tracked
- Travel cooldowns reset on app restart

## Future Expansion Hooks

The system is designed to support:
- Additional locations with complex unlock chains
- Dynamic story progression based on visit counts
- Location-specific loot tables
- Prestige/reset mechanics tied to exploration milestones
- Environmental effects that modify combat
