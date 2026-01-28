import 'package:flutter/foundation.dart';
import 'lunar_game_service.dart';

class UpgradeRecipe {
  final int moonlightCost;
  final Map<String, int> itemCosts;
  final String description;

  const UpgradeRecipe({
    required this.moonlightCost,
    required this.itemCosts,
    required this.description,
  });
}

class InventoryService extends ChangeNotifier {
  final LunarGameService _gameService;

  static const int maxWeaponTier = 5;
  static const int maxArmorTier = 5;

  static const Map<int, UpgradeRecipe> weaponUpgrades = {
    1: UpgradeRecipe(
      moonlightCost: 50,
      itemCosts: {'shadow_essence': 3, 'wolf_claw': 2},
      description: 'Basic Fang Blade (+5 damage)',
    ),
    2: UpgradeRecipe(
      moonlightCost: 120,
      itemCosts: {'shadow_essence': 5, 'wolf_fang': 3, 'moon_essence': 2},
      description: 'Moonlit Edge (+8 damage, +5% crit)',
    ),
    3: UpgradeRecipe(
      moonlightCost: 250,
      itemCosts: {'moon_essence': 8, 'lunar_claw': 4, 'moon_crystal': 2},
      description: 'Lunar Reaver (+12 damage, +10% crit)',
    ),
    4: UpgradeRecipe(
      moonlightCost: 500,
      itemCosts: {'moon_crystal': 5, 'lunar_claw': 8, 'moon_essence': 15},
      description: 'Eclipse Fang (+18 damage, +15% crit)',
    ),
    5: UpgradeRecipe(
      moonlightCost: 1000,
      itemCosts: {'moon_crystal': 10, 'lunar_claw': 15, 'shadow_essence': 20},
      description: 'Celestial Howl (+25 damage, +25% crit)',
    ),
  };

  static const Map<int, UpgradeRecipe> armorUpgrades = {
    1: UpgradeRecipe(
      moonlightCost: 40,
      itemCosts: {'shadow_essence': 2, 'wolf_fang': 1},
      description: 'Shadow Pelt (+3 defense)',
    ),
    2: UpgradeRecipe(
      moonlightCost: 100,
      itemCosts: {'moon_essence': 4, 'wolf_claw': 3},
      description: 'Lunar Guard (+6 defense)',
    ),
    3: UpgradeRecipe(
      moonlightCost: 220,
      itemCosts: {'moon_essence': 7, 'lunar_claw': 3, 'moon_crystal': 1},
      description: 'Moonward Mantle (+10 defense)',
    ),
    4: UpgradeRecipe(
      moonlightCost: 450,
      itemCosts: {'moon_crystal': 4, 'lunar_claw': 6, 'moon_essence': 12},
      description: 'Eclipse Plate (+15 defense)',
    ),
    5: UpgradeRecipe(
      moonlightCost: 900,
      itemCosts: {'moon_crystal': 8, 'lunar_claw': 12, 'shadow_essence': 18},
      description: 'Celestial Mantle (+22 defense)',
    ),
  };

  InventoryService(this._gameService);

  Map<String, int> get inventory => _gameService.playerState.inventory;
  int get weaponLevel => _gameService.playerState.weaponTier;
  int get armorLevel => _gameService.playerState.armorTier;

  void addItem(String itemId, int amount) {
    final player = _gameService.playerState;
    final newInventory = Map<String, int>.from(player.inventory);
    newInventory[itemId] = (newInventory[itemId] ?? 0) + amount;
    _gameService.updatePlayerState(player.copyWith(inventory: newInventory));
    notifyListeners();
  }

  bool hasItems(Map<String, int> requirements) {
    final inventory = _gameService.playerState.inventory;
    for (final entry in requirements.entries) {
      if ((inventory[entry.key] ?? 0) < entry.value) {
        return false;
      }
    }
    return true;
  }

  void consumeItems(Map<String, int> items) {
    final player = _gameService.playerState;
    final newInventory = Map<String, int>.from(player.inventory);
    for (final entry in items.entries) {
      newInventory[entry.key] = (newInventory[entry.key] ?? 0) - entry.value;
      if (newInventory[entry.key]! <= 0) {
        newInventory.remove(entry.key);
      }
    }
    _gameService.updatePlayerState(player.copyWith(inventory: newInventory));
    notifyListeners();
  }

  bool canUpgradeWeapon() {
    final player = _gameService.playerState;
    if (player.weaponTier >= maxWeaponTier) return false;
    
    final recipe = weaponUpgrades[player.weaponTier + 1];
    if (recipe == null) return false;
    
    return player.moonlight >= recipe.moonlightCost && hasItems(recipe.itemCosts);
  }

  bool canUpgradeArmor() {
    final player = _gameService.playerState;
    if (player.armorTier >= maxArmorTier) return false;
    
    final recipe = armorUpgrades[player.armorTier + 1];
    if (recipe == null) return false;
    
    return player.moonlight >= recipe.moonlightCost && hasItems(recipe.itemCosts);
  }

  String? upgradeWeapon() {
    final player = _gameService.playerState;
    if (!canUpgradeWeapon()) return null;
    
    final nextTier = player.weaponTier + 1;
    final recipe = weaponUpgrades[nextTier]!;
    
    _gameService.updateMoonlight(player.moonlight - recipe.moonlightCost);
    consumeItems(recipe.itemCosts);
    
    final damageBoost = _getWeaponDamageBoost(nextTier);
    final critBoost = _getWeaponCritBoost(nextTier);
    
    _gameService.updatePlayerState(player.copyWith(
      weaponTier: nextTier,
      baseDamage: player.baseDamage + damageBoost,
      critRate: player.critRate + critBoost,
    ));
    
    notifyListeners();
    return recipe.description;
  }

  String? upgradeArmor() {
    final player = _gameService.playerState;
    if (!canUpgradeArmor()) return null;
    
    final nextTier = player.armorTier + 1;
    final recipe = armorUpgrades[nextTier]!;
    
    _gameService.updateMoonlight(player.moonlight - recipe.moonlightCost);
    consumeItems(recipe.itemCosts);
    
    final defenseBoost = _getArmorDefenseBoost(nextTier);
    
    _gameService.updatePlayerState(player.copyWith(
      armorTier: nextTier,
      baseDefense: player.baseDefense + defenseBoost,
    ));
    
    notifyListeners();
    return recipe.description;
  }

  int _getWeaponDamageBoost(int tier) {
    switch (tier) {
      case 1: return 5;
      case 2: return 8;
      case 3: return 12;
      case 4: return 18;
      case 5: return 25;
      default: return 0;
    }
  }

  double _getWeaponCritBoost(int tier) {
    switch (tier) {
      case 1: return 0.0;
      case 2: return 0.05;
      case 3: return 0.10;
      case 4: return 0.15;
      case 5: return 0.25;
      default: return 0.0;
    }
  }

  int _getArmorDefenseBoost(int tier) {
    switch (tier) {
      case 1: return 3;
      case 2: return 6;
      case 3: return 10;
      case 4: return 15;
      case 5: return 22;
      default: return 0;
    }
  }

  int getItemCount(String itemId) {
    return _gameService.playerState.inventory[itemId] ?? 0;
  }
}
