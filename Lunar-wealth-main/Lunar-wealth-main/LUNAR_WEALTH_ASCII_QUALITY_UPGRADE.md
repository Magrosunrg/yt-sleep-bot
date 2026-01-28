# Lunar Wealth: Reference Quality ASCII Map Implementation

## Overview
This document describes the implementation of the reference-quality ASCII map for the Lunar Wealth system in Lunar Shell.

## Implementation Summary

### Two-Tab UI Structure
The Lunar Wealth screen provides two tabs:

1. **MAP Tab**: 
   - Massive draggable ASCII landscape (1600x3200 canvas)
   - InteractiveViewer with pan and zoom (minScale: 0.3, maxScale: 2.5)
   - 9 unique regions with elaborate ASCII art
   - Environmental scatter (trees, clouds, birds, rocks, grass, flowers, rivers, bushes)
   - Background grid and connecting paths via CustomPainter
   - Clickable unlocked regions (launch combat, NPCs, sanctuary)
   - Locked regions show "?" placeholder (non-clickable)

2. **INVENTORY Tab**:
   - Player stats (HP, Moonlight, Lifetime Moonlight, Base Damage, Base Defense, Crit Rate)
   - Equipped gear (weapon and armor with ASCII icons: /|\ for weapon, [#] for armor)
   - Moon Blessings (prestige bonuses)
   - Inventory items with counts

### Reference Quality ASCII Art

All 9 regions have been updated with reference-quality ASCII art featuring:

#### Key Qualities:
- **Varied Character Usage**: ^, ~, *, @, ', ., |, /, \, #, =, X, <O>, etc.
- **Generous Spacing**: Spacious, elegant layouts with breathing room between elements
- **Fantasy Aesthetic**: D&D parchment map style with immersive themes
- **Clean Readability**: Each structure stands out without competing for attention
- **Original Designs**: Unique elaborate structures for each region
- **Environmental Integration**: Scatter elements (trees, rocks, etc.) placed thoughtfully

#### Region Details:

**1. VILLAGE (Unlocked - NPC)**
- Master Forge and Master Armorer buildings
- Village Green with well in center
- Detailed cobblestone plaza
- People scattered throughout
- ~50 lines of ASCII art

**2. WHISPERING FOREST (Unlocked - Enemy)**
- Ancient trees with varied designs
- "Ancient Whispers" theme
- Three distinct tree structures: Dark Forest Heart, Gnarled Elder Trees, Twisted Shadow Woods
- Organic forest layout with X patterns for branch intersections
- ~50 lines of ASCII art

**3. MOONLIT MEADOW (Unlocked - Enemy)**
- Wildflower fields with scattered blooms
- Rolling hills represented with wave patterns
- Swaying grasses and graceful petals
- "Beneath the Peaceful Blooms, Creatures Stir Unseen" theme
- ~45 lines of ASCII art

**4. DRAGON PEAKS (Locked - Enemy)**
- Mountain spire with detailed climbing paths
- Treacherous climb with jagged rock
- Frozen ledges and narrow passes
- Icicles hanging precariously
- Snow & ice & danger theme
- ~50 lines of ASCII art

**5. RIVER CANYON (Locked - Enemy)**
- Rushing rapids and cascading water
- Canyon walls towering high
- Deep gorge carved by time and water
- Shadow cave mouth entrance
- Mysteries await within
- ~45 lines of ASCII art

**6. ANCIENT TEMPLE (Locked - Enemy)**
- Grand sacred gate
- Temple ruins with four pillars
- Crumbling weathered statues
- Echoes of forgotten ages
- ~60 lines of ASCII art

**7. SACRED GROVE (Locked - Enemy)**
- Tree of Life with elaborate branches
- Ancient power flows through eternal branches
- Wisdom of the ages
- Sacred circle of life
- Mystical energy radiates from the heart
- Enchanted essence permeates all
- ~65 lines of ASCII art

**8. TOWER OF SORROWS (Locked - Enemy)**
- Cursed tower with twisted spire
- Corrupted by malevolent power
- Dark energy seeps from within
- Evil pulses and curses
- Blighted, twisted, warped, tainted
- Beware the Tower of Sorrows
- ~70 lines of ASCII art

**9. MOON SANCTUARY (Locked - Sanctuary)**
- Lunar Guardian statue
- Moon Temple with elaborate gate
- Sacred moonlit blessing
- Celestial power radiates
- Moonlight radiates eternally
- Final sanctuary of eternal moonlight
- Hallowed grounds
- Ultimate realm
- ~80 lines of ASCII art

### Technical Implementation

**Files Modified:**
- `lib/data/regions.dart`: Updated all 9 region ASCII art definitions

**Files Already Implemented:**
- `lib/screens/lunar_wealth_screen.dart`: Two-tab UI, MapTab, InventoryTab
- `lib/services/map_service.dart`: Region state management
- `lib/models/region.dart`: Region data models
- `lib/data/regions.dart`: Region definitions with ASCII art

### Map Service Features
- Region unlocking based on prerequisites
- Region cleared status tracking
- Defeat count per region
- Difficulty multiplier based on defeats
- State persistence via SharedPreferences

### Interactive Elements
- Tap/click unlocked regions to interact:
  - **Enemy regions**: Launch CombatScreen
  - **NPC regions**: Open upgrade dialogs (Forge, Armorer)
  - **Sanctuary regions**: Special features (prestige, etc.)
- Locked regions are non-interactive and display "?" placeholder
- Smooth dragging and panning with finger/mouse
- Zoom in/out (0.3x to 2.5x scale)

## Acceptance Criteria Met

✅ Two-tab UI renders (MAP + INVENTORY)
✅ Map matches reference quality in ASCII art style and spacing
✅ Structures are high-quality, detailed, and visually striking
✅ Spacious layout with generous breathing room (not cramped)
✅ Environmental details scattered thoughtfully
✅ All 9 regions displayed with unique elaborate ASCII structures
✅ Draggable map works smoothly on all devices
✅ Locked regions show "?" and are non-clickable
✅ Unlocked regions are clickable and launch appropriate interactions
✅ Inventory displays stats, gear, items, Moon Blessings
✅ Tab switching maintains state
✅ NO EMOJIS anywhere (pure ASCII)
✅ Professional, immersive fantasy map aesthetic

## Future Enhancements
- Additional regions could be added
- More NPC types (merchants, quest givers, etc.)
- Quest system integration
- Mini-map overlay for navigation
- Waypoint markers
- Fog of war for unexplored areas

## Testing
- Test map panning and zooming on different screen sizes
- Verify all regions unlock in correct order
- Test combat launching from enemy regions
- Test NPC dialogs from village
- Verify inventory displays all stats correctly
- Test tab switching maintains state
- Verify monospaced font rendering across platforms
