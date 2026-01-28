import 'dart:convert';
import 'package:shared_preferences/shared_preferences.dart';

class StorageService {
  late SharedPreferences _prefs;

  Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  Future<void> saveJson(String key, Map<String, dynamic> data) async {
    final jsonString = jsonEncode(data);
    await _prefs.setString(key, jsonString);
  }

  Map<String, dynamic>? loadJson(String key) {
    final jsonString = _prefs.getString(key);
    if (jsonString == null) return null;
    return jsonDecode(jsonString) as Map<String, dynamic>;
  }

  Future<void> clear(String key) async {
    await _prefs.remove(key);
  }

  Future<void> clearAll() async {
    await _prefs.clear();
  }

  bool hasKey(String key) {
    return _prefs.containsKey(key);
  }
}
