import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class MainNavigationBar extends StatelessWidget {
  final StatefulNavigationShell navigationShell;

  const MainNavigationBar({required this.navigationShell, super.key});

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: navigationShell.currentIndex,
      onDestinationSelected: navigationShell.goBranch,
      destinations: const [
        NavigationDestination(
          key: Key('files-navigation-destination'),
          icon: Icon(Icons.folder_outlined),
          selectedIcon: Icon(Icons.folder),
          label: 'Files',
        ),
        NavigationDestination(
          key: Key('shared-navigation-destination'),
          icon: Icon(Icons.people_outline),
          selectedIcon: Icon(Icons.people),
          label: 'Shared with me',
        ),
      ],
    );
  }
}
