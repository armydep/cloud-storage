import 'package:cloudestorage/features/push/application/push_providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

class SettingsScreen extends ConsumerWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(pushControllerProvider);
    final controller = ref.read(pushControllerProvider.notifier);

    ref.listen(pushControllerProvider, (previous, next) {
      if (next.permissionDenied && previous?.permissionDenied != true) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Notification permission was not granted. You can allow it '
              'from your device settings and try again.',
            ),
          ),
        );
      }
      if (next.error != null && previous?.error != next.error) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(next.error!)));
      }
    });

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        children: [
          SwitchListTile(
            key: const Key('push-enabled-switch'),
            title: const Text('Push notifications'),
            subtitle: const Text(
              'Get notified on this device when something happens, like a '
              'file being shared with you.',
            ),
            value: state.isEnabled,
            onChanged: state.isLoading
                ? null
                : (value) => value ? controller.enable() : controller.disable(),
            secondary: state.isLoading
                ? const SizedBox(
                    width: 24,
                    height: 24,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : null,
          ),
        ],
      ),
    );
  }
}
