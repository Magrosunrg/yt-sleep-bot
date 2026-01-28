import 'package:flutter/foundation.dart';
import 'lunar_game_service.dart';
import 'inventory_service.dart';
import '../models/vendor_item.dart';

class VendorService extends ChangeNotifier {
  final LunarGameService _gameService;
  final InventoryService _inventoryService;

  // Shop inventory data
  static final List<ShopItem> baseShopInventory = [
    ShopItem(
      id: 'health_potion',
      name: 'Health Potion',
      description: 'Restores 20 HP instantly',
      moonlightCost: 15,
      gives: {'health_potion': 1},
      minDifficulty: 1,
      maxStock: 8,
    ),
    ShopItem(
      id: 'shadow_bomb',
      name: 'Shadow Bomb',
      description: 'Deals 15 damage to all enemies',
      moonlightCost: 25,
      gives: {'shadow_bomb': 1},
      minDifficulty: 3,
      maxStock: 3,
    ),
    ShopItem(
      id: 'lunar_dagger',
      name: 'Lunar Dagger',
      description: 'Weapon: +4 damage, +3% crit',
      moonlightCost: 60,
      gives: {'lunar_dagger': 1},
      minDifficulty: 4,
      maxStock: 2,
    ),
    ShopItem(
      id: 'moon_amulet',
      name: 'Moon Amulet',
      description: 'Accessory: +5 defense, +2 HP regen',
      moonlightCost: 80,
      gives: {'moon_amulet': 1},
      minDifficulty: 5,
      maxStock: 2,
    ),
    ShopItem(
      id: 'crystal_sword',
      name: 'Crystal Sword',
      description: 'Weapon: +8 damage, +8% crit',
      moonlightCost: 120,
      gives: {'crystal_sword': 1},
      minDifficulty: 6,
      maxStock: 1,
    ),
    ShopItem(
      id: 'shadow_armor',
      name: 'Shadow Armor',
      description: 'Armor: +10 defense, +5 max HP',
      moonlightCost: 100,
      gives: {'shadow_armor': 1},
      minDifficulty: 5,
      maxStock: 2,
    ),
  ];

  // Forge recipes data
  static const List<ForgeItem> forgeRecipes = [
    ForgeItem(
      id: 'enhanced_health_potion',
      name: 'Enhanced Health Potion',
      description: 'Restores 40 HP instantly',
      cost: {'health_potion': 2, 'moon_essence': 3},
      moonlightCost: 20,
      gives: {'enhanced_health_potion': 1},
      minDifficulty: 3,
    ),
    ForgeItem(
      id: 'shadow_bomb',
      name: 'Shadow Bomb',
      description: 'Deals 15 damage to all enemies',
      cost: {'shadow_essence': 3, 'moon_crystal': 1},
      moonlightCost: 35,
      gives: {'shadow_bomb': 1},
      minDifficulty: 5,
    ),
    ForgeItem(
      id: 'lunar_dagger',
      name: 'Lunar Dagger',
      description: 'Weapon: +4 damage, +3% crit',
      cost: {'lunar_claw': 5, 'moon_essence': 8, 'shadow_essence': 2},
      moonlightCost: 40,
      gives: {'lunar_dagger': 1},
      minDifficulty: 4,
      isWeapon: true,
    ),
    ForgeItem(
      id: 'moon_amulet',
      name: 'Moon Amulet',
      description: 'Accessory: +5 defense, +2 HP regen',
      cost: {'moon_crystal': 4, 'lunar_claw': 3, 'moon_essence': 6},
      moonlightCost: 50,
      gives: {'moon_amulet': 1},
      minDifficulty: 5,
    ),
    ForgeItem(
      id: 'crystal_sword',
      name: 'Crystal Sword',
      description: 'Weapon: +8 damage, +8% crit',
      cost: {'moon_crystal': 8, 'lunar_claw': 10, 'shadow_essence': 5},
      moonlightCost: 60,
      gives: {'crystal_sword': 1},
      minDifficulty: 6,
      isWeapon: true,
    ),
    ForgeItem(
      id: 'shadow_armor',
      name: 'Shadow Armor',
      description: 'Armor: +10 defense, +5 max HP',
      cost: {'shadow_essence': 8, 'moon_crystal': 5, 'lunar_claw': 6},
      moonlightCost: 45,
      gives: {'shadow_armor': 1},
      minDifficulty: 5,
    ),
  ];

  // Current shop inventory (mutable)
  List<ShopItem> currentShopInventory = [];

  // Sell prices for common items
  static const Map<String, int> sellPrices = {
    'shadow_essence': 2,
    'moon_crystal': 5,
    'lunar_claw': 3,
    'moon_essence': 4,
    'wolf_claw': 1,
    'wolf_fang': 2,
    'health_potion': 8,
    'enhanced_health_potion': 20,
    'shadow_bomb': 12,
    'lunar_dagger': 25,
    'moon_amulet': 35,
    'crystal_sword': 50,
    'shadow_armor': 40,
  };

  VendorService(this._gameService, this._inventoryService) {
    _initializeShopInventory();
  }

  void _initializeShopInventory() {
    currentShopInventory = baseShopInventory.map((item) =>
      item.copyWith(currentStock: item.maxStock)
    ).toList();
  }

  // Shop methods
  List<ShopItem> getShopItems(int difficultyLevel) {
    return currentShopInventory.where((item) => 
      item.minDifficulty <= difficultyLevel
    ).toList();
  }

  bool canPurchaseItem(ShopItem item) {
    return _gameService.playerState.moonlight >= item.moonlightCost && 
           item.currentStock > 0;
  }

  String? purchaseItem(ShopItem item) {
    if (!canPurchaseItem(item)) {
      if (_gameService.playerState.moonlight < item.moonlightCost) {
        return 'Not enough moonlight';
      }
      if (item.currentStock <= 0) return 'Out of stock';
      return 'Cannot purchase this item';
    }

    final itemIndex = currentShopInventory.indexWhere((i) => i.id == item.id);
    if (itemIndex == -1) return 'Item not found';

    // Deduct moonlight
    _gameService.updateMoonlight(_gameService.playerState.moonlight - item.moonlightCost);

    // Update stock
    currentShopInventory[itemIndex] = currentShopInventory[itemIndex].copyWith(
      currentStock: currentShopInventory[itemIndex].currentStock - 1
    );

    // Add item to inventory
    for (final entry in item.gives.entries) {
      _inventoryService.addItem(entry.key, entry.value);
    }

    notifyListeners();
    return 'Purchased ${item.name}';
  }

  // Sell methods
  int getSellPrice(String itemId) {
    return sellPrices[itemId] ?? 1;
  }

  String? sellItem(String itemId, int amount) {
    final currentAmount = _inventoryService.getItemCount(itemId);
    if (currentAmount < amount) return 'Not enough items to sell';

    final totalValue = getSellPrice(itemId) * amount;

    // Remove items from inventory
    _inventoryService.consumeItems({itemId: amount});

    // Add moonlight
    _gameService.updateMoonlight(_gameService.playerState.moonlight + totalValue);

    notifyListeners();
    return 'Sold $amount $itemId for $totalValue moonlight';
  }

  // Forge methods
  List<ForgeItem> getForgeRecipes(int difficultyLevel) {
    return forgeRecipes.where((recipe) => 
      recipe.minDifficulty <= difficultyLevel
    ).toList();
  }

  bool canCraftItem(ForgeItem item) {
    if (_gameService.playerState.moonlight < item.moonlightCost) return false;
    
    for (final entry in item.cost.entries) {
      if ((_gameService.playerState.inventory[entry.key] ?? 0) < entry.value) {
        return false;
      }
    }
    return true;
  }

  String? craftItem(ForgeItem item) {
    if (!canCraftItem(item)) return 'Cannot craft this item';

    // Deduct moonlight cost
    _gameService.updateMoonlight(_gameService.playerState.moonlight - item.moonlightCost);

    // Consume materials
    _inventoryService.consumeItems(item.cost);

    // Add crafted item to inventory
    for (final entry in item.gives.entries) {
      _inventoryService.addItem(entry.key, entry.value);
    }

    notifyListeners();
    return 'Crafted ${item.name}';
  }

  // Refresh shop stock (call after certain exploration milestones)
  void refreshShopStock() {
    _initializeShopInventory();
    notifyListeners();
  }
}