# Exploration System Test Checklist

## Acceptance Criteria from Ticket

- [ ] Players can travel between multiple areas via the new ExplorationScreen
- [ ] Each area spawns its configured enemies
- [ ] New areas unlock after meeting milestones
- [ ] All world-state updates are reflected correctly after app restart

## Detailed Test Cases

### Initial State
- [ ] App starts with Moonlit Clearing unlocked
- [ ] Home screen shows "1" unlocked location
- [ ] Home screen lists "Moonlit Clearing" under unlocked locations

### Exploration Screen
- [ ] Navigate to Exploration screen from home screen
- [ ] Current location shows as "Moonlit Clearing"
- [ ] ASCII map displays correctly
- [ ] Flavor text appears
- [ ] "Hunt for Prey" button is available
- [ ] Explorations counter starts at 0

### Combat Integration
- [ ] Click "Hunt for Prey" button
- [ ] Combat screen launches with a Shadow Wolf (100% spawn rate in Moonlit Clearing)
- [ ] Enemy appears correctly with ASCII art
- [ ] Combat functions normally (attack, guard, use moonlight)
- [ ] After victory, return to exploration screen
- [ ] Explorations counter increments by 1

### Unlocking Silver Pines
- [ ] After defeating 5 Shadow Wolves, return to exploration screen
- [ ] "Available to Unlock" section appears
- [ ] Silver Pines shows with "[UNLOCK]" button
- [ ] Click unlock button
- [ ] Success message appears
- [ ] Silver Pines moves to unlocked locations list
- [ ] Silver Pines story beat displays

### Story Beats
- [ ] First visit to a location shows story beat screen
- [ ] Click "[CONTINUE]" to dismiss
- [ ] Story beat does not show again on subsequent visits

### Travel
- [ ] Click on Silver Pines to travel
- [ ] Location changes to Silver Pines
- [ ] ASCII map and flavor text update
- [ ] Try to travel immediately again - should show cooldown timer
- [ ] Wait 3 seconds, travel becomes available again

### Enemy Spawning - Silver Pines
- [ ] Hunt for prey in Silver Pines multiple times
- [ ] Should encounter both Shadow Wolves (~60%) and Moon Wolves (~40%)
- [ ] Both enemy types function correctly in combat

### Unlocking Crater Rim
- [ ] Collect 100 total moonlight
- [ ] Crater Rim appears in "Available to Unlock"
- [ ] Unlock Crater Rim
- [ ] Travel to Crater Rim
- [ ] Story beat displays

### Enemy Spawning - Crater Rim
- [ ] Hunt for prey in Crater Rim multiple times
- [ ] Should encounter Shadow Wolves (~30%) and Moon Wolves (~70%)

### Persistence
- [ ] Close and restart the app
- [ ] Current location is preserved
- [ ] Unlocked locations are preserved
- [ ] Visit counts are preserved
- [ ] Story beats already viewed don't show again
- [ ] Can continue exploring from where you left off

### Integration with Existing Systems
- [ ] Moonlight earned in combat appears in player stats
- [ ] HP updates correctly during and after combat
- [ ] Home screen shows correct number of unlocked locations
- [ ] Location names display correctly on home screen

## Known Issues / Edge Cases

### To Verify:
- Travel cooldown timing precision
- Encounter generation randomness distribution
- Story beat display on rapid navigation
- Memory usage with multiple location visits
