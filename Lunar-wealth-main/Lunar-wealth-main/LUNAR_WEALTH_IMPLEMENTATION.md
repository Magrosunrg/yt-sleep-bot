# Lunar Wealth Implementation Summary

## Overview
Implemented a two-tab UI system for Lunar Wealth featuring:
1. An interactive draggable ASCII map with 9 regions
2. A comprehensive inventory and stats tab
3. Region unlocking progression system
4. Integration with existing combat and upgrade systems

## New Files Created

### Models
- `lib/models/region.dart` - Region and RegionState models
  - `Region`: Defines region properties (name, type, ASCII art, position, unlock requirements)
  - `RegionType`: Enum for enemy, npc, and sanctuary regions
  - `RegionState`: Tracks unlock status, clear status, and defeat counts per region

### Data
- `lib/data/regions.dart` - Static region definitions
  - 9 regions: Village, Forest, Meadow, Mountains, Cave, Ancient Temple, Sacred Grove, Cursed Tower, Moon Sanctuary
  - Each region has unique ASCII art, map coordinates, and unlock prerequisites

### Services
- `lib/services/map_service.dart` - Manages map state and region progression
  - Tracks region unlock status
  - Manages region cleared status and defeat counts
  - Handles region unlocking based on prerequisites
  - Persists state via StorageService

### Screens
- `lib/screens/lunar_wealth_screen.dart` - Main two-tab interface
  - `LunarWealthScreen`: Tab container with bottom navigation
  - `MapTab`: Interactive scrollable map with all regions
  - `InventoryTab`: Player stats, equipped gear, and inventory items
  - `NPCDialog`: Upgrade interface for Forge and Armorer

## Region System

### Starting Regions (Unlocked)
- Village: NPC hub with Forge and Armorer
- Forest: Enemy region (shadow_wolf)
- Meadow: Enemy region (shadow_wolf)

### Locked Regions (Progressive Unlocking)
- Mountains: Unlocks after beating Forest
- Cave: Unlocks after beating Meadow
- Ancient Temple: Unlocks after beating Mountains
- Sacred Grove: Unlocks after beating Cave
- Cursed Tower: Unlocks after beating Ancient Temple
- Moon Sanctuary: Unlocks after beating Sacred Grove + Cursed Tower

### Region Features
- **Enemy Regions**: Launch combat screen, track defeats, increase difficulty on repeat
- **NPC Regions**: Open upgrade dialogs (Forge for weapons, Armorer for armor)
- **Sanctuary Regions**: Special regions for prestige/restoration features
- **Locked Regions**: Display "?" with unlock requirements until prerequisites met

## Map Interaction

### Draggable Map
- Uses `InteractiveViewer` for smooth panning and zooming
- Fixed 500x1400 container with positioned regions
- Monospaced font ensures consistent ASCII art rendering
- Pinch-to-zoom: 0.5x to 2.0x scale range

### Visual States
- **Unlocked**: Shows ASCII art with region name, tappable
- **Cleared**: Gold border, displays defeat count
- **Locked**: Grey border, shows "?" and unlock requirements

## Combat Integration
- Tapping enemy regions launches existing CombatScreen
- On victory: Region marked as cleared, defeat count incremented
- Defeat count affects region difficulty multiplier (10% per defeat)
- Auto-unlocks dependent regions after clearing prerequisites

## Inventory Tab
Displays:
- Player Stats: HP, Moonlight, Lifetime Moonlight, Base Damage/Defense, Crit Rate
- Equipped Gear: Weapon Tier, Armor Tier
- Moon Blessings: Prestige count and multipliers (if any)
- Inventory Items: All collected materials with quantities

## State Persistence
- Region unlock status persists via `StorageService`
- Cleared status and defeat counts saved per region
- Integrates with existing prestige system (resets on prestige)

## Integration Updates

### Modified Files
- `lib/main.dart`: Added MapService to DI
- `lib/services/prestige_service.dart`: Added MapService reset on prestige
- `lib/screens/home_screen.dart`: Added navigation button to Lunar Wealth
- `test/widget_test.dart`: Updated test to include MapService

## Usage
1. Launch app, navigate to "LUNAR WEALTH" from home screen
2. Drag map to explore different regions
3. Tap unlocked regions to interact (combat or NPCs)
4. Switch to INVENTORY tab to view stats and items
5. Progress through regions by defeating enemies and unlocking new areas

## Future Enhancements
- Additional NPC types (Witch, Magic Cat) in locked regions
- Moon Sanctuary prestige integration
- Dynamic enemy types per region
- Region-specific loot tables
- Story beats triggered by region discoveries
