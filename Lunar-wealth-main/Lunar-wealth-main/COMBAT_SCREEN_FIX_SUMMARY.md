# Combat Screen Blank/White Display Fix

## Problem
The combat screen was appearing as a blank/white screen when entering a fight, with no enemy display, HP bars, buttons, or any visible content.

## Root Causes Identified

1. **Missing Loading State**: The screen was rendering before combat initialization completed
   - The `startCombat()` call happens in `addPostFrameCallback`, so the first render occurs before combat is initialized
   - Initial `combatSnapshot` is empty with all zero values
   
2. **No Error Handling**: Any exceptions during rendering would cause a blank white screen
   - No try-catch blocks around critical rendering code
   - No error boundaries to catch and display errors
   
3. **Missing Color Specifications**: Some UI elements lacked explicit colors
   - AppBar text and icons didn't specify colors, could inherit white-on-white
   
4. **Unsafe State Access**: Potential null reference errors
   - Accessing player/enemy state without validation
   - No fallback values for invalid snapshot data

## Fixes Applied

### 1. Added Loading State (Lines 218-240)
```dart
// Show loading state if combat hasn't initialized yet
if (!combatService.isInCombat && combatService.combatState.enemy == null) {
  return Center(
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Text('INITIALIZING COMBAT...'),
        CircularProgressIndicator(),
      ],
    ),
  );
}
```
**Why**: Provides visual feedback while combat initializes, prevents rendering with invalid data

### 2. Added Comprehensive Error Handling (Lines 180-294, 297-361)
- Wrapped entire build method in try-catch
- Added error boundaries in ValueListenableBuilder
- Created `_buildErrorState()` widget to display user-friendly error messages
- Added debug logging with stack traces

**Why**: Catches exceptions and displays helpful error messages instead of blank white screen

### 3. Enhanced `initState` Error Handling (Lines 74-99)
- Added try-catch around combat initialization
- Added null checks before accessing playerState
- Navigates back on initialization failure

**Why**: Prevents crashes during screen initialization, provides graceful degradation

### 4. Fixed Color Specifications (Lines 167, 171, 197)
- Explicitly set AppBar title text color to `Color(0xFFE0E0E0)`
- Set back button icon color to `Color(0xFFE0E0E0)`

**Why**: Ensures text is visible against dark background, prevents white-on-white rendering

### 5. Improved `_checkForDamage` Method (Lines 123-161)
- Added try-catch wrapper
- Added initialization checks for `_lastPlayerHp` and `_lastEnemyHp`
- Only triggers damage animation if last values are valid (> 0)
- Added debug logging for errors

**Why**: Prevents errors when HP tracking variables aren't initialized properly

### 6. Enhanced Player Section Rendering (Lines 357-425)
- Added fallback logic for invalid snapshot values
- Uses actual player HP if snapshot has invalid (0) values
```dart
final playerHp = snapshot.playerMaxHp > 0 ? snapshot.playerHp : player.hp;
final playerMaxHp = snapshot.playerMaxHp > 0 ? snapshot.playerMaxHp : player.maxHp;
```

**Why**: Ensures HP bars display correctly even if snapshot hasn't updated yet

### 7. Improved Combat Log Section (Lines 614-680)
- Added empty state with "Awaiting combat..." message
- Checks if log is empty before rendering ScrollView

**Why**: Provides visual feedback when combat hasn't started yet, prevents empty log area

### 8. Safer Damage Check Triggering (Lines 210-216)
- Only schedules damage check callback if combat is active
- Added mounted check before calling setState

**Why**: Prevents unnecessary callbacks and potential setState errors

## Testing Recommendations

1. **Test Combat Initialization**
   - Navigate to combat from Exploration screen
   - Navigate to combat from Lunar Wealth map
   - Verify loading state shows briefly then transitions to combat UI

2. **Test Error Scenarios**
   - Try combat with invalid enemy ID (should show error state)
   - Test with corrupted combat state
   - Verify error messages are displayed instead of blank screen

3. **Test Visual Display**
   - Verify all text is visible (not white-on-white)
   - Check HP bars display correctly
   - Confirm action buttons appear
   - Verify combat log shows messages

4. **Test Edge Cases**
   - Fast navigation (clicking multiple times)
   - Background/foreground app lifecycle
   - Low HP scenarios
   - Victory/defeat states

## Files Modified

- `/lib/screens/combat_screen.dart` - Main combat screen implementation

## Summary

The blank/white screen issue was caused by a combination of factors:
1. Screen rendering before combat initialization
2. Lack of error handling causing silent failures
3. Missing color specifications
4. Unsafe state access

All issues have been addressed with proper loading states, comprehensive error handling, explicit color specifications, and defensive programming practices. The combat screen will now:
- Show a loading state during initialization
- Display helpful error messages if something goes wrong
- Render correctly with all text visible
- Handle edge cases gracefully
