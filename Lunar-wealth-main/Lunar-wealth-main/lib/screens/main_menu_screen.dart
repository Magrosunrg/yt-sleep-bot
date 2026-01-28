import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../utils/color_extensions.dart';
import 'exploration_log_screen.dart';
import 'settings_screen.dart';

class MainMenuScreen extends StatelessWidget {
  const MainMenuScreen({super.key});

  void _onExplorePressed(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => const ExplorationLogScreen(),
      ),
    );
  }

  void _onSettingsPressed(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => const SettingsScreen(),
      ),
    );
  }

  void _onQuitPressed() {
    SystemNavigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    final height = size.height;
    final width = size.width;

    final double horizontalPadding = (width * 0.05).clamp(16.0, 32.0);
    final double verticalPadding = (height * 0.05).clamp(12.0, 24.0);
    final double titleFontSize = (height * 0.025).clamp(8.0, 12.0);
    final double titleSpacing = (height * 0.03).clamp(8.0, 20.0);
    final double buttonWidth = (width * 0.25).clamp(180.0, 280.0);
    final double buttonHeight = (height * 0.12).clamp(35.0, 50.0);
    final double buttonFontSize = (height * 0.03).clamp(10.0, 16.0);
    final double buttonSpacing = (width * 0.03).clamp(12.0, 24.0);
    final double footerSpacing = (height * 0.02).clamp(6.0, 12.0);

    return Scaffold(
      backgroundColor: const Color(0xFF000000),
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.symmetric(
            horizontal: horizontalPadding,
            vertical: verticalPadding,
          ),
          child: Column(
            children: [
              // Title at the top
              _buildTitle(titleFontSize),
              SizedBox(height: titleSpacing),
              
              // Horizontal button layout in the middle
              Expanded(
                child: Center(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      _buildMenuButton(
                        'EXPLORE',
                        () => _onExplorePressed(context),
                        const Color(0xFFFFD700),
                        buttonWidth,
                        buttonHeight,
                        buttonFontSize,
                      ),
                      SizedBox(width: buttonSpacing),
                      _buildMenuButton(
                        'SETTINGS',
                        () => _onSettingsPressed(context),
                        const Color(0xFF87CEEB),
                        buttonWidth,
                        buttonHeight,
                        buttonFontSize,
                      ),
                      SizedBox(width: buttonSpacing),
                      _buildMenuButton(
                        'QUIT',
                        _onQuitPressed,
                        const Color(0xFFFF6B6B),
                        buttonWidth,
                        buttonHeight,
                        buttonFontSize,
                      ),
                    ],
                  ),
                ),
              ),
              
              // Footer at the bottom
              SizedBox(height: footerSpacing),
              const Text(
                'A Candy Box-inspired text adventure',
                style: TextStyle(
                  fontFamily: 'Courier',
                  fontSize: 10,
                  color: Color(0xFF666666),
                ),
              ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTitle(double fontSize) {
    return Text(
      '''
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     ██╗     ██╗   ██╗███╗   ██╗ █████╗ ██████╗          ║
║     ██║     ██║   ██║████╗  ██║██╔══██╗██╔══██╗         ║
║     ██║     ██║   ██║██╔██╗ ██║███████║██████╔╝         ║
║     ██║     ██║   ██║██║╚██╗██║██╔══██║██╔══██╗         ║
║     ███████╗╚██████╔╝██║ ╚████║██║  ██║██║  ██║         ║
║     ╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚═╝  ╚═╝         ║
║                                                           ║
║        ███████╗██╗  ██╗███████╗██╗     ██╗               ║
║        ██╔════╝██║  ██║██╔════╝██║     ██║               ║
║        ███████╗███████║█████╗  ██║     ██║               ║
║        ╚════██║██╔══██║██╔══╝  ██║     ██║               ║
║        ███████║██║  ██║███████╗███████╗███████╗          ║
║        ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝          ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
      ''',
      style: TextStyle(
        fontFamily: 'Courier',
        fontSize: fontSize,
        color: const Color(0xFFFFD700),
        height: 1.0,
      ),
      textAlign: TextAlign.center,
    );
  }

  Widget _buildMenuButton(
    String label,
    VoidCallback onPressed,
    Color color,
    double width,
    double height,
    double fontSize,
  ) {
    return SizedBox(
      width: width,
      height: height,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color, width: 2),
          backgroundColor: color.withValues(alpha: 0.1),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        child: Text(
          '[ $label ]',
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: fontSize,
            fontWeight: FontWeight.bold,
            color: color,
            letterSpacing: 2,
          ),
        ),
      ),
    );
  }
}
