import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'services/storage_service.dart';
import 'services/lunar_game_service.dart';
import 'services/inventory_service.dart';
import 'services/exploration_service.dart';
import 'services/exploration_log_service.dart';
import 'services/combat_service.dart';
import 'services/building_service.dart';
import 'services/settings_service.dart';
import 'screens/main_menu_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.landscapeLeft,
    DeviceOrientation.landscapeRight,
  ]);

  final storageService = StorageService();
  await storageService.init();

  final settingsService = SettingsService(storageService);
  final gameService = LunarGameService(storageService);
  final inventoryService = InventoryService(gameService);
  final explorationService = ExplorationService(storageService, gameService);
  final explorationLogService = ExplorationLogService(
    storageService,
    gameService,
    settingsService: settingsService,
  );
  final combatService = CombatService(gameService);
  final buildingService = BuildingService();

  runApp(LunarShellApp(
    storageService: storageService,
    gameService: gameService,
    inventoryService: inventoryService,
    explorationService: explorationService,
    explorationLogService: explorationLogService,
    combatService: combatService,
    buildingService: buildingService,
    settingsService: settingsService,
  ));
}

class LunarShellApp extends StatelessWidget {
  final StorageService storageService;
  final LunarGameService gameService;
  final InventoryService inventoryService;
  final ExplorationService explorationService;
  final ExplorationLogService explorationLogService;
  final CombatService combatService;
  final BuildingService buildingService;
  final SettingsService settingsService;

  const LunarShellApp({
    super.key,
    required this.storageService,
    required this.gameService,
    required this.inventoryService,
    required this.explorationService,
    required this.explorationLogService,
    required this.combatService,
    required this.buildingService,
    required this.settingsService,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<StorageService>.value(
          value: storageService,
        ),
        ChangeNotifierProvider<LunarGameService>.value(
          value: gameService,
        ),
        ChangeNotifierProvider<InventoryService>.value(
          value: inventoryService,
        ),
        ChangeNotifierProvider<ExplorationService>.value(
          value: explorationService,
        ),
        ChangeNotifierProvider<ExplorationLogService>.value(
          value: explorationLogService,
        ),
        ChangeNotifierProvider<CombatService>.value(
          value: combatService,
        ),
        ChangeNotifierProvider<BuildingService>.value(
          value: buildingService,
        ),
        ChangeNotifierProvider<SettingsService>.value(
          value: settingsService,
        ),
      ],
      child: MaterialApp(
        title: 'Lunar Shell',
        debugShowCheckedModeBanner: false,
        theme: ThemeData(
          useMaterial3: true,
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFFFFFFFF),
            brightness: Brightness.dark,
            surface: const Color(0xFF000000),
            onSurface: const Color(0xFFFFFFFF),
          ),
          scaffoldBackgroundColor: const Color(0xFF000000),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF000000),
            foregroundColor: Color(0xFFFFFFFF),
          ),
          textTheme: const TextTheme(
            bodyLarge: TextStyle(fontFamily: 'Courier', color: Color(0xFFFFFFFF)),
            bodyMedium: TextStyle(fontFamily: 'Courier', color: Color(0xFFFFFFFF)),
            bodySmall: TextStyle(fontFamily: 'Courier', color: Color(0xFFFFFFFF)),
            titleLarge: TextStyle(fontFamily: 'Courier', color: Color(0xFFFFFFFF)),
            titleMedium: TextStyle(fontFamily: 'Courier', color: Color(0xFFFFFFFF)),
            titleSmall: TextStyle(fontFamily: 'Courier', color: Color(0xFFFFFFFF)),
          ),
        ),
        home: const MainMenuScreen(),
      ),
    );
  }
}
