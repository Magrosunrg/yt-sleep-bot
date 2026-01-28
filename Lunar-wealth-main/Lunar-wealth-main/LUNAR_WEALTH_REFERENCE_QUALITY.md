# Lunar Wealth: MAP and INVENTORY Tabs - Reference Quality Implementation

## Overview
Implemented a two-tab UI for the Lunar Wealth screen with high-quality ASCII art and professional formatting.

## TAB 1 - MAP (Reference Quality)
The MAP tab provides an immersive, draggable ASCII world map with:

### Features
- **Massive draggable canvas**: 1600x3200 pixels using InteractiveViewer
- **Zoom and pan**: minScale 0.3, maxScale 2.5 for exploring the detailed map
- **9 detailed regions** with elaborate ASCII art:
  1. **Village** - Detailed forge and armorer buildings (NPC zone)
  2. **Whispering Forest** - Mystical forest with gnarled trees (Enemy)
  3. **Moonlit Meadow** - Peaceful grassland with wildflowers (Enemy)
  4. **Dragon Peaks** - Towering mountain range with ice (Enemy)
  5. **Shadow Canyon** - Deep gorge with rushing river (Enemy)
  6. **Ancient Temple** - Ruins with pillars and sacred gate (Enemy)
  7. **Enchanted Grove** - Sacred forest with Tree of Life (Enemy)
  8. **Tower of Sorrows** - Twisted cursed tower (Enemy)
  9. **Lunar Sanctum** - Final celestial temple (Sanctuary)

### Visual Style
- **Spacious layout**: Generous breathing room between regions
- **Environmental scatter**: Birds, clouds, trees, mountains, rocks, grass, flowers, rivers
- **Background grid**: Subtle grid pattern with connecting paths
- **Region presentation**: Plain text name above ASCII art (NO BOXES)
- **Progressive unlocking**: Regions unlock based on clearing prerequisites
- **Status indicators**: Cleared status, defeat counts, locked placeholders

### Interactive Elements
- Tap regions to launch combat encounters
- Tap Village for NPC interactions (forge/armorer)
- Draggable map with finger panning
- Visual feedback on region states

## TAB 2 - INVENTORY (Reference Quality)

### ASCII Art Header
Large ASCII art "INVENTORY" title in gold color at the top

### Equipped Gear Section
Professional bordered container with:
- **Section header**: Bordered ASCII frame "EQUIPPED GEAR & STATS"
- **Weapon display**:
  - Large ASCII art of equipped weapon (tier-specific designs)
  - Weapon name prominently displayed
  - Damage stat (with prestige multiplier)
  - Crit Rate percentage
  - Special ability description (for upgraded weapons)
- **Armor display**:
  - Large ASCII art of equipped armor (tier-specific designs)
  - Armor name prominently displayed
  - Defense stat (with prestige multiplier)
  - Special ability description (for upgraded armor)
- **Player stats**:
  - Max HP
  - Current HP with visual HP bar (gradient: red for damage, green for healing)
  - Moonlight balance (gold color)
  - Lifetime moonlight collected

### Inventory Grid Section
Professional 4-column grid layout:
- **Section header**: Bordered ASCII frame "INVENTORY ITEMS"
- **Grid specifications**:
  - 4 columns of inventory slots
  - Minimum 12 slots displayed (3 rows)
  - Automatic expansion for more items
- **Filled slots**:
  - Item-specific ASCII icon (mapped by item ID)
  - Quantity counter (gold color)
  - Dark bordered container
- **Empty slots**:
  - "- -" placeholder text
  - Subtle border and darker background
  - Clear visual distinction from filled slots

### Moon Blessings Section
(Displayed if prestige count > 0)
- **Section header**: Bordered ASCII frame "MOON BLESSINGS"
- **Stats displayed**:
  - Prestige count
  - Damage bonus percentage
  - Defense bonus percentage
  - Loot bonus percentage

## Technical Implementation

### Weapon ASCII Art (Tier 0-5)
Six unique weapon designs ranging from rusty blade to celestial howl

### Armor ASCII Art (Tier 0-5)
Six unique armor designs ranging from tattered cloak to celestial mantle

### Item Icons
Mapped ASCII icons for:
- shadow_essence: ~*~
- wolf_claw: /|\
- wolf_fang: >|<
- moon_essence: (o)
- lunar_claw: /^\\
- moon_crystal: <*>
- ancient_relic: [!]
- healing_potion: (+)
- mana_potion: (~)
- key_fragment: [K]
- mysterious_orb: (@)
- enchanted_gem: <#>

### Visual Design Standards
- **Font**: Courier monospaced throughout
- **Color palette**:
  - Background: 0xFF1A1A2E
  - Dark elements: 0xFF0F0F23
  - Gold highlights: 0xFFFFD700
  - Silver text: 0xFFC0C0C0, 0xFFE0E0E0
  - Gray text: 0xFF808080
- **Borders**: ASCII box-drawing characters (╔═╗║╚╝) and standard ASCII (|, -, =)
- **Spacing**: Consistent padding and margins for readability

### Tab Navigation
- Bottom tab bar with "MAP" and "INVENTORY" buttons
- Visual feedback (gold border) on selected tab
- Icons for each tab (map, inventory_2)
- Smooth transitions between tabs
- State maintained when switching

## Key Files Modified
- `/lib/screens/lunar_wealth_screen.dart`: Complete redesign of InventoryTab, MAP tab already implemented

## User Experience
- **Immersive**: High-quality ASCII art creates fantasy/D&D parchment map aesthetic
- **Professional**: Clean borders, organized sections, clear hierarchy
- **Informative**: All relevant stats and items clearly displayed
- **Interactive**: Tap to interact with regions, smooth navigation
- **Scrollable**: Inventory tab scrolls if needed, map pans and zooms
- **Accessible**: Clear visual feedback, no emojis (pure ASCII)

## Acceptance Criteria Met
✅ Two-tab UI renders (MAP + INVENTORY)
✅ Map matches reference quality and style
✅ Inventory matches reference quality and layout
✅ Equipped weapon display with ASCII art and stats
✅ Equipped armor display with ASCII art
✅ Inventory grid organized with borders and slots (4 columns)
✅ Player stats visible (HP, Moonlight, etc.)
✅ Tab switching works smoothly
✅ Draggable map with zoom/pan
✅ Inventory scrollable if needed
✅ NO EMOJIS anywhere
✅ Professional, immersive fantasy aesthetic

## Portrait Orientation
System locked to portrait mode via SystemChrome in main.dart
