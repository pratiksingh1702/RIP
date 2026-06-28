import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:rip_app/data/models/message.dart';
import 'package:rip_app/utils/date_formatter.dart';
import '../../providers/chat_provider.dart';
import '../../providers/settings_provider.dart';

import 'project_list.dart';
import '../overlays/add_repo_sheet.dart';
import 'package:go_router/go_router.dart';

class AppDrawer extends ConsumerStatefulWidget {
  const AppDrawer({super.key});

  @override
  ConsumerState<AppDrawer> createState() => _AppDrawerState();
}

class _AppDrawerState extends ConsumerState<AppDrawer> {
  @override
  Widget build(BuildContext context) {
    final themeMode = ref.watch(themeModeProvider);
    final messages = ref.watch(chatProvider);

    Map<DateTime, List<Message>> _groupMessagesByDate(List<Message> messages) {
      final Map<DateTime, List<Message>> grouped = {};
      for (final msg in messages) {
        final date = DateTime(msg.timestamp.year, msg.timestamp.month, msg.timestamp.day);
        if (!grouped.containsKey(date)) {
          grouped[date] = [];
        }
        grouped[date]!.add(msg);
      }
      return grouped;
    }

    final groupedMessages = _groupMessagesByDate(messages);
    final sortedDates = groupedMessages.keys.toList()..sort((a, b) => b.compareTo(a));

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          const DrawerHeader(
            decoration: BoxDecoration(
              color: Colors.blue,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.code, size: 48, color: Colors.white),
                SizedBox(height: 8),
                Text(
                  'RIP',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 24,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.add),
            title: const Text('Add Repository'),
            onTap: () {
              showModalBottomSheet(
                context: context,
                isScrollControlled: true,
                builder: (context) => const AddRepoSheet(),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.folder),
            title: const Text('Projects'),
            onTap: () {
              showDialog(
                context: context,
                builder: (context) => Dialog(
                  child: SizedBox(
                    height: 400,
                    child: ProjectList(),
                  ),
                ),
              );
            },
          ),
          const Divider(),
          if (messages.isNotEmpty) ...[
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Text(
                'Chat History',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
            ),
            for (final date in sortedDates)
              ExpansionTile(
                title: Text(DateFormatter.formatDate(date)),
                children: [
                  for (final msg in groupedMessages[date]!.take(10))
                    ListTile(
                      leading: Icon(msg.isUser ? Icons.person : Icons.smart_toy),
                      title: Text(
                        msg.content,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                      ),
                      subtitle: Text(DateFormatter.formatTime(msg.timestamp)),
                      onTap: () {
                        Navigator.pop(context);
                      },
                    ),
                ],
              ),
            const Divider(),
          ],
          ListTile(
            leading: const Icon(Icons.history),
            title: const Text('Clear Chat History'),
            onTap: () async {
              await ref.read(chatProvider.notifier).clearChat();
              if (context.mounted) {
                Navigator.pop(context);
              }
            },
          ),
          const Divider(),
          ExpansionTile(
            leading: const Icon(Icons.palette),
            title: const Text('Theme'),
            children: [
              ListTile(
                title: const Text('Light'),
                trailing: themeMode == ThemeMode.light
                    ? const Icon(Icons.check)
                    : null,
                onTap: () {
                  ref
                      .read(settingsNotifierProvider.notifier)
                      .saveThemeMode(ThemeMode.light);
                },
              ),
              ListTile(
                title: const Text('Dark'),
                trailing: themeMode == ThemeMode.dark
                    ? const Icon(Icons.check)
                    : null,
                onTap: () {
                  ref
                      .read(settingsNotifierProvider.notifier)
                      .saveThemeMode(ThemeMode.dark);
                },
              ),
              ListTile(
                title: const Text('System'),
                trailing: themeMode == ThemeMode.system
                    ? const Icon(Icons.check)
                    : null,
                onTap: () {
                  ref
                      .read(settingsNotifierProvider.notifier)
                      .saveThemeMode(ThemeMode.system);
                },
              ),
            ],
          ),
          ListTile(
            leading: const Icon(Icons.settings),
            title: const Text('Server Settings'),
            onTap: () {
              context.go('/setup');
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.info),
            title: const Text('About RIP'),
            onTap: () {},
          ),
        ],
      ),
    );
  }
}
