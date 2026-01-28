# Passive Healing Implementation

## Overview
Implemented passive healing mechanic where the character heals slowly back to full HP when not in combat.

## Features Implemented

### 1. Core Healing Mechanics
- **Healing Rate**: 1.5% of max HP per second (~2 HP/second for 100 max HP)
- **Tick Interval**: 500ms (0.5 seconds)
- **Per Tick Healing**: ~1 HP per tick (ceiling of max HP * 0.015 * 0.5)
- **Healing Duration**: ~50 seconds to heal from 1 HP to 100 HP

### 2. Combat Integration
- Healing stops immediately when combat starts
- Healing resumes automatically when combat ends
- Combat state tracked via `LunarGameService.setCombatState(bool)`

### 3. State Persistence
- HP already persisted through PlayerState
- Healing automatically resumes on app launch if HP < max and not in combat
- App lifecycle handling (pause/resume) properly manages healing timer

### 4. UI Display
- **HP Bar in Inventory Tab**:
  - Visual HP bar showing current/max HP
  - Color changes based on healing state:
    - Green gradient when healing (0xFF90EE90 to 0xFF50C878)
    - Red gradient when not healing (0xFFDC143C to 0xFF8B0000)
  - Text indicator "(Healing...)" shown when actively healing
  - Bar width reflects HP percentage

## Files Modified

### 1. `/lib/services/lunar_game_service.dart`
**Changes:**
- Added healing timer (`Timer? _healingTimer`)
- Added combat state tracking (`bool _isInCombat`)
- Added healing constants:
  - `_healingTickInterval = 500ms`
  - `_healingPercentPerSecond = 0.015` (1.5%)
- Added methods:
  - `setCombatState(bool inCombat)` - Called by CombatService to track combat state
  - `_startHealingIfNeeded()` - Starts healing if conditions are met
  - `_stopHealing()` - Stops healing timer
  - `_healTick()` - Processes healing tick
  - `onAppPaused()` - Pauses healing and saves state
  - `onAppResumed()` - Resumes healing
- Added `isHealing` getter for UI feedback
- Modified `updateHp()` to restart healing when HP changes outside combat
- Modified `updatePlayerState()` to check healing after state updates
- Added `dispose()` to clean up timer

### 2. `/lib/services/combat_service.dart`
**Changes:**
- Modified `startCombat()` to call `_gameService.setCombatState(true)`
- Modified `endCombat()` to call `_gameService.setCombatState(false)`
- Modified `_loadCombatState()` to set combat state on app launch if combat is active

### 3. `/lib/screens/lunar_wealth_screen.dart`
**Changes:**
- Added `WidgetsBindingObserver` mixin to `_LunarWealthScreenState`
- Implemented lifecycle methods:
  - `initState()` - Registers observer
  - `dispose()` - Removes observer
  - `didChangeAppLifecycleState()` - Handles app pause/resume
- Modified `InventoryTab.build()` to show HP bar instead of simple stat row
- Added `_buildHpBar()` method:
  - Displays HP text with healing indicator
  - Shows visual HP bar with gradient
  - Changes color based on healing state

## Implementation Details

### Healing Flow

#### 1. App Startup
```
LunarGameService constructor
  ↓
_loadState() - Load player HP
  ↓
_startHealingIfNeeded() - Start healing if HP < max and not in combat
```

#### 2. Combat Start
```
CombatService.startCombat()
  ↓
_gameService.setCombatState(true)
  ↓
_stopHealing() - Stop healing timer
```

#### 3. Combat End
```
CombatService.endCombat()
  ↓
_gameService.setCombatState(false)
  ↓
_startHealingIfNeeded() - Resume healing if HP < max
```

#### 4. Healing Tick
```
Timer.periodic (every 500ms)
  ↓
_healTick()
  ↓
Calculate heal amount (max HP * 1.5% * 0.5)
  ↓
updateHp(new HP)
  ↓
Stop timer if HP >= max
```

### Edge Cases Handled

1. **Prestige Reset**: When player resets via prestige, HP is restored to 100/100 and healing doesn't start (already at max)
2. **App Launch with Active Combat**: Healing briefly starts then immediately stops when CombatService loads combat state
3. **HP Updates Outside Combat**: Healing restarts automatically when HP is updated outside combat (e.g., from consumables)
4. **Multiple Healing Timers**: Timer is cancelled before creating new one to prevent duplicates
5. **HP Already at Max**: Healing doesn't start if HP is already at max

## Testing Checklist

- [x] Healing starts when HP < max and not in combat
- [x] Healing stops when combat starts
- [x] Healing resumes when combat ends
- [x] HP bar shows correct percentage
- [x] Healing indicator displays when healing is active
- [x] HP bar color changes based on healing state
- [x] App pause stops healing and saves state
- [x] App resume restarts healing if needed
- [x] Prestige reset properly restores HP
- [x] No healing during combat
- [x] Healing stops when HP reaches max
- [x] HP persists through app restart

## Performance Considerations

- Timer runs every 500ms (minimal CPU impact)
- Timer automatically stops when healing completes
- Single timer instance (no duplicate timers)
- Efficient HP updates with state persistence
- No unnecessary UI rebuilds (only when HP or healing state changes)

## Visual Design

The HP bar follows the existing Lunar Shell aesthetic:
- Monospaced Courier font
- Dark lunar color palette
- Subtle green glow for healing (peaceful, calming)
- Red gradient for combat/danger (standard HP bar color)
- Border matches existing UI elements
- Minimal visual clutter (healing indicator only shows when active)
