class PlayerState {
  String playerName;
  int hp;
  int maxHp;
  int moonlight;
  List<String> unlockedLocations;
  Map<String, int> inventory;
  int weaponTier;
  int armorTier;
  int baseDamage;
  int baseDefense;
  double critRate;
  Map<String, int> resources;
  bool isInBuildRun;

  PlayerState({
    required this.playerName,
    required this.hp,
    required this.maxHp,
    required this.moonlight,
    required this.unlockedLocations,
    Map<String, int>? inventory,
    this.weaponTier = 0,
    this.armorTier = 0,
    this.baseDamage = 15,
    this.baseDefense = 0,
    this.critRate = 0.0,
    Map<String, int>? resources,
    this.isInBuildRun = false,
  }) : inventory = inventory ?? {}, resources = resources ?? {};

  factory PlayerState.initial() {
    return PlayerState(
      playerName: 'Lone Wolf',
      hp: 100,
      maxHp: 100,
      moonlight: 0,
      unlockedLocations: ['moonlit_clearing'],
      inventory: {},
      weaponTier: 0,
      armorTier: 0,
      baseDamage: 15,
      baseDefense: 0,
      critRate: 0.0,
      resources: {},
      isInBuildRun: false,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'playerName': playerName,
      'hp': hp,
      'maxHp': maxHp,
      'moonlight': moonlight,
      'unlockedLocations': unlockedLocations,
      'inventory': inventory,
      'weaponTier': weaponTier,
      'armorTier': armorTier,
      'baseDamage': baseDamage,
      'baseDefense': baseDefense,
      'critRate': critRate,
      'resources': resources,
      'isInBuildRun': isInBuildRun,
    };
  }

  factory PlayerState.fromJson(Map<String, dynamic> json) {
    return PlayerState(
      playerName: json['playerName'] as String,
      hp: json['hp'] as int,
      maxHp: json['maxHp'] as int,
      moonlight: json['moonlight'] as int,
      unlockedLocations: List<String>.from(json['unlockedLocations'] as List),
      inventory: json['inventory'] != null 
          ? Map<String, int>.from(json['inventory'] as Map)
          : {},
      weaponTier: json['weaponTier'] as int? ?? 0,
      armorTier: json['armorTier'] as int? ?? 0,
      baseDamage: json['baseDamage'] as int? ?? 15,
      baseDefense: json['baseDefense'] as int? ?? 0,
      critRate: (json['critRate'] as num?)?.toDouble() ?? 0.0,
      resources: json['resources'] != null 
          ? Map<String, int>.from(json['resources'] as Map)
          : {},
      isInBuildRun: json['isInBuildRun'] as bool? ?? false,
    );
  }

  PlayerState copyWith({
    String? playerName,
    int? hp,
    int? maxHp,
    int? moonlight,
    List<String>? unlockedLocations,
    Map<String, int>? inventory,
    int? weaponTier,
    int? armorTier,
    int? baseDamage,
    int? baseDefense,
    double? critRate,
    Map<String, int>? resources,
    bool? isInBuildRun,
  }) {
    return PlayerState(
      playerName: playerName ?? this.playerName,
      hp: hp ?? this.hp,
      maxHp: maxHp ?? this.maxHp,
      moonlight: moonlight ?? this.moonlight,
      unlockedLocations: unlockedLocations ?? List.from(this.unlockedLocations),
      inventory: inventory ?? Map.from(this.inventory),
      weaponTier: weaponTier ?? this.weaponTier,
      armorTier: armorTier ?? this.armorTier,
      baseDamage: baseDamage ?? this.baseDamage,
      baseDefense: baseDefense ?? this.baseDefense,
      critRate: critRate ?? this.critRate,
      resources: resources ?? Map.from(this.resources),
      isInBuildRun: isInBuildRun ?? this.isInBuildRun,
    );
  }
}
