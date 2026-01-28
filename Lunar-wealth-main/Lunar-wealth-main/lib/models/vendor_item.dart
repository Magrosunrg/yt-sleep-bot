class ShopItem {
  final String id;
  final String name;
  final String description;
  final int moonlightCost;
  final Map<String, int> gives;
  final int minDifficulty;
  final int maxStock;
  int currentStock;

  ShopItem({
    required this.id,
    required this.name,
    required this.description,
    required this.moonlightCost,
    required this.gives,
    this.minDifficulty = 1,
    this.maxStock = 5,
    this.currentStock = 5,
  });

  ShopItem copyWith({
    String? id,
    String? name,
    String? description,
    int? moonlightCost,
    Map<String, int>? gives,
    int? minDifficulty,
    int? maxStock,
    int? currentStock,
  }) {
    return ShopItem(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      moonlightCost: moonlightCost ?? this.moonlightCost,
      gives: gives ?? this.gives,
      minDifficulty: minDifficulty ?? this.minDifficulty,
      maxStock: maxStock ?? this.maxStock,
      currentStock: currentStock ?? this.currentStock,
    );
  }

  factory ShopItem.fromJson(Map<String, dynamic> json) {
    return ShopItem(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String,
      moonlightCost: json['moonlightCost'] as int,
      gives: Map<String, int>.from(json['gives'] as Map),
      minDifficulty: json['minDifficulty'] as int? ?? 1,
      maxStock: json['maxStock'] as int? ?? 5,
      currentStock: json['currentStock'] as int? ?? 5,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'moonlightCost': moonlightCost,
      'gives': gives,
      'minDifficulty': minDifficulty,
      'maxStock': maxStock,
      'currentStock': currentStock,
    };
  }
}

class ForgeItem {
  final String id;
  final String name;
  final String description;
  final Map<String, int> cost;
  final int moonlightCost;
  final Map<String, int> gives;
  final int minDifficulty;
  final bool isWeapon;

  const ForgeItem({
    required this.id,
    required this.name,
    required this.description,
    required this.cost,
    required this.moonlightCost,
    required this.gives,
    this.minDifficulty = 1,
    this.isWeapon = false,
  });

  factory ForgeItem.fromJson(Map<String, dynamic> json) {
    return ForgeItem(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String,
      cost: Map<String, int>.from(json['cost'] as Map),
      moonlightCost: json['moonlightCost'] as int,
      gives: Map<String, int>.from(json['gives'] as Map),
      minDifficulty: json['minDifficulty'] as int? ?? 1,
      isWeapon: json['isWeapon'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'description': description,
      'cost': cost,
      'moonlightCost': moonlightCost,
      'gives': gives,
      'minDifficulty': minDifficulty,
      'isWeapon': isWeapon,
    };
  }
}