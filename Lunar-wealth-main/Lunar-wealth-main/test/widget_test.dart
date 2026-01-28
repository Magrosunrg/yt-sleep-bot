import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:lunar_shell/services/storage_service.dart';
import 'package:lunar_shell/services/lunar_game_service.dart';
import 'package:lunar_shell/services/inventory_service.dart';
import 'package:lunar_shell/services/exploration_service.dart';
import 'package:lunar_shell/services/exploration_log_service.dart';
import 'package:lunar_shell/services/combat_service.dart';
import 'package:lunar_shell/services/building_service.dart';
import 'package:lunar_shell/services/settings_service.dart';
import 'package:lunar_shell/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    
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

    await tester.pumpWidget(LunarShellApp(
      storageService: storageService,
      gameService: gameService,
      inventoryService: inventoryService,
      explorationService: explorationService,
      explorationLogService: explorationLogService,
      combatService: combatService,
      buildingService: buildingService,
      settingsService: settingsService,
    ));

    expect(find.text('[ EXPLORE ]'), findsOneWidget);
    expect(find.text('[ SETTINGS ]'), findsOneWidget);
    expect(find.text('[ QUIT ]'), findsOneWidget);
  });
}
