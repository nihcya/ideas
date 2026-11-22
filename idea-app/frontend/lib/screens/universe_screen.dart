import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';
import '../widgets/universe_graph_view.dart';

class UniverseScreen extends ConsumerStatefulWidget {
  final String ideaId;
  const UniverseScreen({super.key, required this.ideaId});

  @override
  ConsumerState<UniverseScreen> createState() => _UniverseScreenState();
}

class _UniverseScreenState extends ConsumerState<UniverseScreen> {
  int _depth = 2;
  String _direction = 'both';
  bool _includeInspired = true;
  late Future<Map<String, dynamic>> _graph;

  @override
  void initState() {
    super.initState();
    _load();
  }

  void _load() {
    _graph = ref.read(universeServiceProvider).getGraph(
      widget.ideaId,
      depth: _depth,
      direction: _direction,
      includeInspired: _includeInspired,
    );
  }

  void _change({int? depth, String? direction, bool? includeInspired}) {
    setState(() {
      _depth = depth ?? _depth;
      _direction = direction ?? _direction;
      _includeInspired = includeInspired ?? _includeInspired;
      _load();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('创意宇宙'),
        actions: [
          IconButton(
            tooltip: '刷新图谱',
            onPressed: () => setState(_load),
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: Wrap(
              alignment: WrapAlignment.center,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 8,
              runSpacing: 8,
              children: [
                const Text('层级'),
                for (final value in [1, 2, 3])
                  ChoiceChip(
                    label: Text('$value 层'),
                    selected: _depth == value,
                    onSelected: (_) => _change(depth: value),
                  ),
                const SizedBox(width: 8),
                DropdownButton<String>(
                  value: _direction,
                  items: const [
                    DropdownMenuItem(value: 'both', child: Text('上下游')),
                    DropdownMenuItem(value: 'ancestors', child: Text('仅上游')),
                    DropdownMenuItem(value: 'descendants', child: Text('仅下游')),
                  ],
                  onChanged: (value) => _change(direction: value),
                ),
                FilterChip(
                  label: const Text('包含 Inspired'),
                  selected: _includeInspired,
                  onSelected: (value) => _change(includeInspired: value),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: FutureBuilder<Map<String, dynamic>>(
              future: _graph,
              builder: (context, snapshot) {
                if (snapshot.connectionState == ConnectionState.waiting) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.hub_outlined, size: 42),
                          const SizedBox(height: 12),
                          Text('图谱加载失败：${snapshot.error}', textAlign: TextAlign.center),
                          const SizedBox(height: 12),
                          FilledButton.tonal(onPressed: () => setState(_load), child: const Text('重试')),
                        ],
                      ),
                    ),
                  );
                }
                final graph = snapshot.data!;
                final truncated = graph['truncated'] == true;
                return Column(
                  children: [
                    if (truncated)
                      const MaterialBanner(
                        content: Text('图谱已达到节点或边数量上限，可调整层级或方向查看局部关系'),
                        actions: [SizedBox.shrink()],
                      ),
                    Expanded(
                      child: UniverseGraphView(
                        graph: graph,
                        onNodeTap: (id) => context.push('/idea/$id'),
                      ),
                    ),
                    _Legend(),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _Legend extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    const items = [
      (Color(0xFF2A9D8F), 'Fork'),
      (Color(0xFF7B61A8), 'Merge'),
      (Color(0xFFE09F3E), 'Evolve'),
      (Color(0xFFD65A8A), 'Inspired'),
      (Color(0xFF9CA3AF), '受限来源'),
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 14),
      child: Wrap(
        alignment: WrapAlignment.center,
        spacing: 14,
        runSpacing: 8,
        children: items.map((item) => Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 9,
              height: 9,
              decoration: BoxDecoration(color: item.$1, shape: BoxShape.circle),
            ),
            const SizedBox(width: 5),
            Text(item.$2, style: Theme.of(context).textTheme.labelSmall),
          ],
        )).toList(),
      ),
    );
  }
}
