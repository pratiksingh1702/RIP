import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../data/models/project.dart';
import 'connection_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants.dart';

final projectListProvider = FutureProvider.autoDispose<List<Project>>((ref) async {
  final client = ref.watch(ripClientProvider);
  final projects = await client.listProjects();
  
  // Side effect: if the active project is not in the new list, clear it
  final activeId = ref.read(activeProjectIdProvider);
  if (activeId != null && projects.isNotEmpty) {
    final stillExists = projects.any((p) => p.projectId == activeId);
    if (!stillExists) {
      ref.read(activeProjectNotifierProvider.notifier).setActiveProject(null);
    }
  } else if (activeId != null && projects.isEmpty) {
     ref.read(activeProjectNotifierProvider.notifier).setActiveProject(null);
  }
  
  return projects;
});

final activeProjectIdProvider = StateProvider<String?>((ref) {
  return null;
});

final activeProjectProvider = FutureProvider.autoDispose<Project?>((ref) async {
  final projectId = ref.watch(activeProjectIdProvider);
  if (projectId == null) return null;

  final projects = await ref.watch(projectListProvider.future);
  try {
    return projects.firstWhere((p) => p.projectId == projectId);
  } catch (e) {
    return null;
  }
});

class ActiveProjectNotifier extends Notifier<void> {
  @override
  void build() {}

// In rip_app/lib/presentation/providers/project_provider.dart
// Replace the setActiveProject method in ActiveProjectNotifier:

Future<void> setActiveProject(String? projectId) async {
  final prefs = await SharedPreferences.getInstance();
  if (projectId != null) {
    await prefs.setString(AppConstants.sharedPrefsActiveProjectIdKey, projectId);
  } else {
    await prefs.remove(AppConstants.sharedPrefsActiveProjectIdKey);
  }
  ref.read(activeProjectIdProvider.notifier).state = projectId;
  
  // Sync to server
  _syncProjectToServer(projectId);
}

Future<void> _syncProjectToServer(String? projectId) async {
  try {
    final client = ref.read(ripClientProvider);
    if (projectId != null) {
      await client.setActiveProject(projectId);
    } else {
      await client.clearActiveProject();
    }
  } catch (_) {
    // Silently fail - project is still saved locally
  }
}

  Future<void> loadActiveProject() async {
    final prefs = await SharedPreferences.getInstance();
    final savedProjectId = prefs.getString(AppConstants.sharedPrefsActiveProjectIdKey);
    if (savedProjectId != null) {
      ref.read(activeProjectIdProvider.notifier).state = savedProjectId;
    }
  }
}

final activeProjectNotifierProvider =
    NotifierProvider<ActiveProjectNotifier, void>(ActiveProjectNotifier.new);
