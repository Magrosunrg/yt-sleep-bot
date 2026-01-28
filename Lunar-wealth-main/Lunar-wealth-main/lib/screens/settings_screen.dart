import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../utils/color_extensions.dart';
import '../services/settings_service.dart';
import '../services/lunar_game_service.dart';
import '../services/storage_service.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final settingsService = Provider.of<SettingsService>(context);
    final size = MediaQuery.of(context).size;
    final baseFontSize = (size.height * 0.022).clamp(10.0, 14.0);
    final fontSize = baseFontSize * settingsService.textSizeMultiplier;

    return Scaffold(
      backgroundColor: const Color(0xFF1A1A2E),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F0F23),
        title: Text(
          '[ SETTINGS ]',
          style: TextStyle(
            fontFamily: 'Courier',
            fontSize: fontSize,
            color: const Color(0xFFFFD700),
            fontWeight: FontWeight.bold,
            letterSpacing: 2,
          ),
        ),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFFFFD700)),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildSectionHeader('AUDIO SETTINGS', fontSize),
            const SizedBox(height: 12),
            _buildToggleSetting(
              context,
              'Master Volume',
              settingsService.masterVolumeEnabled,
              (value) => settingsService.setMasterVolume(value),
              fontSize,
            ),
            _buildToggleSetting(
              context,
              'Sound Effects',
              settingsService.soundEffectsEnabled,
              (value) => settingsService.setSoundEffects(value),
              fontSize,
            ),
            _buildToggleSetting(
              context,
              'Music',
              settingsService.musicEnabled,
              (value) => settingsService.setMusic(value),
              fontSize,
            ),
            const SizedBox(height: 24),
            _buildSectionHeader('GAME SETTINGS', fontSize),
            const SizedBox(height: 12),
            _buildDropdownSetting(
              context,
              'Game Speed',
              settingsService.gameSpeed,
              ['slow', 'normal', 'fast'],
              (value) => settingsService.setGameSpeed(value!),
              fontSize,
            ),
            _buildDropdownSetting(
              context,
              'Difficulty',
              settingsService.difficulty,
              ['easy', 'normal', 'hard'],
              (value) => settingsService.setDifficulty(value!),
              fontSize,
            ),
            _buildToggleSetting(
              context,
              'Auto-pause on Choice',
              settingsService.autoPauseOnChoice,
              (value) => settingsService.setAutoPauseOnChoice(value),
              fontSize,
            ),
            const SizedBox(height: 24),
            _buildSectionHeader('DISPLAY SETTINGS', fontSize),
            const SizedBox(height: 12),
            _buildDropdownSetting(
              context,
              'Text Size',
              settingsService.textSize,
              ['small', 'normal', 'large'],
              (value) => settingsService.setTextSize(value!),
              fontSize,
            ),
            const SizedBox(height: 24),
            _buildSectionHeader('DATA MANAGEMENT', fontSize),
            const SizedBox(height: 12),
            _buildActionButton(
              context,
              'Save Game',
              const Color(0xFF4CAF50),
              () => _saveGame(context),
              fontSize,
            ),
            const SizedBox(height: 8),
            _buildActionButton(
              context,
              'Load Game',
              const Color(0xFF2196F3),
              () => _loadGame(context),
              fontSize,
            ),
            const SizedBox(height: 8),
            _buildActionButton(
              context,
              'Reset Game',
              const Color(0xFFFF6B6B),
              () => _confirmResetGame(context),
              fontSize,
            ),
            const SizedBox(height: 8),
            _buildActionButton(
              context,
              'Clear Cache',
              const Color(0xFFFFA726),
              () => _clearCache(context),
              fontSize,
            ),
            const SizedBox(height: 24),
            _buildSectionHeader('ABOUT', fontSize),
            const SizedBox(height: 12),
            _buildAboutSection(fontSize),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionHeader(String title, double fontSize) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      decoration: const BoxDecoration(
        border: Border(
          bottom: BorderSide(color: Color(0xFFFFD700), width: 2),
        ),
      ),
      child: Row(
        children: [
          Text(
            '╔═══ ',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFFFD700),
            ),
          ),
          Text(
            title,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFFFD700),
              fontWeight: FontWeight.bold,
              letterSpacing: 1.5,
            ),
          ),
          Expanded(
            child: Text(
              ' ═══╗',
              style: TextStyle(
                fontFamily: 'Courier',
                fontSize: fontSize,
                color: const Color(0xFFFFD700),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleSetting(
    BuildContext context,
    String label,
    bool value,
    ValueChanged<bool> onChanged,
    double fontSize,
  ) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8.0),
      padding: const EdgeInsets.all(12.0),
      decoration: BoxDecoration(
        color: const Color(0xFF0F0F23),
        border: Border.all(color: const Color(0xFF87CEEB), width: 1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFCCCCCC),
            ),
          ),
          _SettingsSwitch(
            value: value,
            onChanged: onChanged,
            activeThumbColor: const Color(0xFFFFD700),
            activeTrackColor: const Color(0xFFFFD700).withValues(alpha: 0.5),
          ),
        ],
      ),
    );
  }

  Widget _buildDropdownSetting(
    BuildContext context,
    String label,
    String value,
    List<String> options,
    Function(String?) onChanged,
    double fontSize,
  ) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8.0),
      padding: const EdgeInsets.all(12.0),
      decoration: BoxDecoration(
        color: const Color(0xFF0F0F23),
        border: Border.all(color: const Color(0xFF87CEEB), width: 1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFCCCCCC),
            ),
          ),
          DropdownButton<String>(
            value: value,
            dropdownColor: const Color(0xFF0F0F23),
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFFFD700),
            ),
            items: options.map((option) {
              return DropdownMenuItem<String>(
                value: option,
                child: Text(
                  option.toUpperCase(),
                  style: TextStyle(
                    fontFamily: 'Courier',
                    fontSize: fontSize,
                    color: const Color(0xFFFFD700),
                  ),
                ),
              );
            }).toList(),
            onChanged: onChanged,
          ),
        ],
      ),
    );
  }

  Widget _buildActionButton(
    BuildContext context,
    String label,
    Color color,
    VoidCallback onPressed,
    double fontSize,
  ) {
    return SizedBox(
      width: double.infinity,
      child: OutlinedButton(
        onPressed: onPressed,
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color, width: 2),
          backgroundColor: color.withValues(alpha: 0.1),
          padding: const EdgeInsets.symmetric(vertical: 12.0),
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

  Widget _buildAboutSection(double fontSize) {
    return Container(
      padding: const EdgeInsets.all(12.0),
      decoration: BoxDecoration(
        color: const Color(0xFF0F0F23),
        border: Border.all(color: const Color(0xFF87CEEB), width: 1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Version: 1.0.0',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFCCCCCC),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Credits:',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFFFD700),
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Inspired by Candy Box 2',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFCCCCCC),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Built with Flutter',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFFCCCCCC),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Contact: support@lunarshell.game',
            style: TextStyle(
              fontFamily: 'Courier',
              fontSize: fontSize,
              color: const Color(0xFF87CEEB),
            ),
          ),
        ],
      ),
    );
  }

  void _saveGame(BuildContext context) async {
    final gameService = Provider.of<LunarGameService>(context, listen: false);
    await gameService.saveState();
    
    if (!context.mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Game saved successfully!',
          style: TextStyle(fontFamily: 'Courier'),
        ),
        backgroundColor: Color(0xFF4CAF50),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _loadGame(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Game loaded from last save!',
          style: TextStyle(fontFamily: 'Courier'),
        ),
        backgroundColor: Color(0xFF2196F3),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _confirmResetGame(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF1A1A2E),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(4),
          side: const BorderSide(color: Color(0xFFFF6B6B), width: 2),
        ),
        title: const Text(
          'CONFIRM RESET',
          style: TextStyle(
            fontFamily: 'Courier',
            color: Color(0xFFFF6B6B),
            fontWeight: FontWeight.bold,
          ),
        ),
        content: const Text(
          'Are you sure you want to reset all game progress?\n\nThis action cannot be undone.',
          style: TextStyle(
            fontFamily: 'Courier',
            color: Color(0xFFCCCCCC),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text(
              'CANCEL',
              style: TextStyle(
                fontFamily: 'Courier',
                color: Color(0xFF87CEEB),
              ),
            ),
          ),
          TextButton(
            onPressed: () {
              Navigator.of(context).pop();
              _resetGame(context);
            },
            child: const Text(
              'RESET',
              style: TextStyle(
                fontFamily: 'Courier',
                color: Color(0xFFFF6B6B),
                fontWeight: FontWeight.bold,
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _resetGame(BuildContext context) async {
    final gameService = Provider.of<LunarGameService>(context, listen: false);
    final storageService = Provider.of<StorageService>(context, listen: false);
    
    gameService.resetGame();
    await storageService.clear('exploration_log_history');
    await storageService.clear('exploration_log_state');
    
    if (!context.mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Game reset complete!',
          style: TextStyle(fontFamily: 'Courier'),
        ),
        backgroundColor: Color(0xFFFF6B6B),
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _clearCache(BuildContext context) async {
    final storageService = Provider.of<StorageService>(context, listen: false);
    await storageService.clear('exploration_log_history');
    
    if (!context.mounted) return;
    
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text(
          'Cache cleared!',
          style: TextStyle(fontFamily: 'Courier'),
        ),
        backgroundColor: Color(0xFFFFA726),
        duration: Duration(seconds: 2),
      ),
    );
  }
}

class _SettingsSwitch extends StatelessWidget {
  final bool value;
  final ValueChanged<bool> onChanged;
  final Color? activeThumbColor;
  final Color? activeTrackColor;

  const _SettingsSwitch({
    required this.value,
    required this.onChanged,
    this.activeThumbColor,
    this.activeTrackColor,
  });

  @override
  Widget build(BuildContext context) {
    return Switch(
      value: value,
      onChanged: onChanged,
      activeThumbColor: activeThumbColor,
      activeTrackColor: activeTrackColor,
    );
  }
}
