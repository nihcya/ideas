import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../providers/api_provider.dart';

/// Bounded, ACL-filtered Idea Universe around a selected Idea.
class IdeaUniverseScreen extends ConsumerStatefulWidget {
  final String ideaId;

  const IdeaUniverseScreen({super.key, required this.ideaId});

  @override
  ConsumerState<IdeaUniverseScreen> createState() => _IdeaUniverseScreenState();
}

class _IdeaUniverseScreenState extends ConsumerState<IdeaUniverseScreen> {
  int _depth = 2;
  String _direction = 'both';
  bool _includeInspired = true;
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _graph;
  int _requestGeneration = 0;
  final Set<String> _removingAssociations = <String>{};

  @override
  void initState() {
    super.initState();
    _loadGraph();
  }

  Future<void> _loadGraph() async {
    final generation = ++_requestGeneration;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final graph = await ref.read(universeServiceProvider).getGraph(
            widget.ideaId,
            depth: _depth,
            direction: _direction,
            includeInspired: _includeInspired,
          );
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _graph = graph;
        _loading = false;
      });
    } catch (error) {
      if (!mounted || generation != _requestGeneration) return;
      setState(() {
        _error = error.toString();
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _requestGeneration++;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(
        title: const Text('创意宇宙'),
        actions: [
          IconButton(
            tooltip: '刷新图谱',
            onPressed: _loading ? null : _loadGraph,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          _buildControls(theme),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? _buildError(theme)
                    : _graph == null
                        ? const Center(child: Text('暂无图谱数据'))
                        : _buildGraph(theme, _graph!),
          ),
        ],
      ),
    );
  }

  Widget _buildControls(ThemeData theme) {
    return Material(
      color: theme.colorScheme.surface,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: 12,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                DropdownButton<int>(
                  value: _depth,
                  isDense: true,
                  underline: const SizedBox.shrink(),
                  items: const [1, 2, 3]
                      .map((value) => DropdownMenuItem(
                            value: value,
                            child: Text('$value 层'),
                          ))
                      .toList(),
                  onChanged: _loading
                      ? null
                      : (value) {
                          if (value == null) return;
                          setState(() => _depth = value);
                          _loadGraph();
                        },
                ),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'both', label: Text('上下游')),
                    ButtonSegment(value: 'ancestors', label: Text('上游')),
                    ButtonSegment(value: 'descendants', label: Text('下游')),
                  ],
                  selected: {_direction},
                  showSelectedIcon: false,
                  onSelectionChanged: _loading
                      ? null
                      : (value) {
                          setState(() => _direction = value.first);
                          _loadGraph();
                        },
                ),
              ],
            ),
            SwitchListTile.adaptive(
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('显示灵感关联'),
              subtitle: const Text('灵感关联不属于创意血缘，也不改变授权'),
              value: _includeInspired,
              onChanged: _loading
                  ? null
                  : (value) {
                      setState(() => _includeInspired = value);
                      _loadGraph();
                    },
            ),
            const Wrap(
              spacing: 14,
              runSpacing: 6,
              children: [
                _LegendDot(color: Color(0xFFB58B42), label: '当前创意'),
                _LegendDot(color: Color(0xFF4C8DCE), label: 'Fork'),
                _LegendDot(color: Color(0xFF8A70C5), label: 'Collide'),
                _LegendDot(color: Color(0xFF4F9B83), label: 'Evolve'),
                _LegendDot(color: Color(0xFF9CA3AF), label: '受限来源'),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildInspiredManager(List<Map<String, dynamic>> edges) {
    final inspired = edges.where((edge) => edge['type'] == 'inspired').toList();
    return ExpansionTile(
      title: const Text('管理灵感关联'),
      subtitle: Text('${inspired.length} 条关联 · 不影响血缘和授权'),
      children: inspired.isEmpty
          ? const [ListTile(title: Text('当前图谱没有灵感关联'))]
          : inspired.map((edge) {
              final id = edge['id'] as String;
              return ListTile(
                leading: const Icon(Icons.lightbulb_outline),
                title: const Text('灵感关联'),
                subtitle: Text(edge['note'] as String? ?? '未填写说明'),
                trailing: IconButton(
                  tooltip: '删除关联',
                  onPressed: _removingAssociations.contains(id)
                      ? null
                      : () => _removeInspired(id),
                  icon: _removingAssociations.contains(id)
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.delete_outline),
                ),
              );
            }).toList(),
    );
  }

  Future<void> _removeInspired(String associationId) async {
    setState(() => _removingAssociations.add(associationId));
    try {
      await ref.read(universeServiceProvider).removeInspired(
            targetIdeaId: widget.ideaId,
            associationId: associationId,
          );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('灵感关联已删除')),
        );
        await _loadGraph();
      }
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('删除失败：$error')),
        );
      }
    } finally {
      if (mounted) setState(() => _removingAssociations.remove(associationId));
    }
  }

  Widget _buildError(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.hub_outlined, size: 40),
            const SizedBox(height: 12),
            Text('图谱加载失败', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: _loadGraph,
              icon: const Icon(Icons.refresh),
              label: const Text('重试'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGraph(ThemeData theme, Map<String, dynamic> graph) {
    final nodes = (graph['nodes'] as List<dynamic>? ?? [])
        .map((value) => Map<String, dynamic>.from(value as Map))
        .toList();
    final edges = (graph['edges'] as List<dynamic>? ?? [])
        .map((value) => Map<String, dynamic>.from(value as Map))
        .toList();
    if (nodes.isEmpty) return const Center(child: Text('暂无可展示的关联创意'));

    final layers = <int, List<Map<String, dynamic>>>{};
    for (final node in nodes) {
      final depth = (node['depth'] as num?)?.toInt() ?? 0;
      layers.putIfAbsent(depth, () => []).add(node);
    }
    final maxDepth = layers.keys.fold<int>(0, (a, b) => a > b ? a : b);
    const width = 900.0;
    final height = 150.0 + (maxDepth + 1) * 190.0;
    final positions = <String, Offset>{};
    for (final entry in layers.entries) {
      final layer = entry.value;
      for (var index = 0; index < layer.length; index++) {
        final x = width * (index + 1) / (layer.length + 1);
        final y = 78.0 + entry.key * 190.0;
        positions[layer[index]['id'] as String] = Offset(x, y);
      }
    }

    return Column(
      children: [
        if (graph['truncated'] == true)
          const MaterialBanner(
            content: Text('图谱已达到节点或关系上限，可调整层级或方向查看局部网络。'),
            leading: Icon(Icons.info_outline),
            actions: [SizedBox.shrink()],
          ),
        Expanded(
          child: InteractiveViewer(
            minScale: 0.35,
            maxScale: 2.5,
            boundaryMargin: const EdgeInsets.all(120),
            constrained: false,
            child: SizedBox(
              width: width,
              height: height,
              child: Stack(
                children: [
                  Positioned.fill(
                    child: CustomPaint(
                      painter: _UniverseEdgePainter(
                        edges: edges,
                        positions: positions,
                        colors: theme.colorScheme,
                      ),
                    ),
                  ),
                  for (final node in nodes)
                    if (positions[node['id']] != null)
                      Positioned(
                        left: positions[node['id']]!.dx - 76,
                        top: positions[node['id']]!.dy - 45,
                        width: 152,
                        height: 90,
                        child: _UniverseNodeCard(
                          node: node,
                          onTap: node['navigable'] == true &&
                                  node['is_root'] != true
                              ? () => context.push('/idea/${node['id']}')
                              : null,
                        ),
                      ),
                ],
              ),
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(8),
          child: Text(
            '${nodes.length} 个节点 · ${edges.length} 条关系 · 可拖动和缩放',
            style: theme.textTheme.bodySmall,
          ),
        ),
        if (graph['can_manage_associations'] == true)
          _buildInspiredManager(edges),
      ],
    );
  }
}

class _LegendDot extends StatelessWidget {
  final Color color;
  final String label;

  const _LegendDot({required this.color, required this.label});

  @override
  Widget build(BuildContext context) => Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircleAvatar(radius: 5, backgroundColor: color),
          const SizedBox(width: 5),
          Text(label, style: Theme.of(context).textTheme.labelSmall),
        ],
      );
}

class _UniverseNodeCard extends StatelessWidget {
  final Map<String, dynamic> node;
  final VoidCallback? onTap;

  const _UniverseNodeCard({required this.node, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final isRestricted = node['node_type'] == 'restricted';
    final isRoot = node['is_root'] == true;
    final color = _parseColor(node['color_hex'] as String?);
    return Card(
      margin: EdgeInsets.zero,
      elevation: isRoot ? 5 : 2,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(14),
        side: BorderSide(
          color: isRoot ? Theme.of(context).colorScheme.primary : color,
          width: isRoot ? 2 : 1,
        ),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    isRestricted ? Icons.lock_outline : Icons.lightbulb_outline,
                    size: 15,
                    color: color,
                  ),
                  const SizedBox(width: 4),
                  Flexible(
                    child: Text(
                      isRoot ? '当前创意' : (isRestricted ? '受限来源' : '创意'),
                      style: Theme.of(context).textTheme.labelSmall,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 5),
              Text(
                node['title'] as String? ?? '未命名创意',
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
              const SizedBox(height: 3),
              Text(
                node['author'] as String? ?? '匿名',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Color _parseColor(String? value) {
    if (value == null || !RegExp(r'^#[0-9A-Fa-f]{6}$').hasMatch(value)) {
      return const Color(0xFF9CA3AF);
    }
    return Color(int.parse('FF${value.substring(1)}', radix: 16));
  }
}

class _UniverseEdgePainter extends CustomPainter {
  final List<Map<String, dynamic>> edges;
  final Map<String, Offset> positions;
  final ColorScheme colors;

  const _UniverseEdgePainter({
    required this.edges,
    required this.positions,
    required this.colors,
  });

  @override
  void paint(Canvas canvas, Size size) {
    for (final edge in edges) {
      final source = positions[edge['source']];
      final target = positions[edge['target']];
      if (source == null || target == null) continue;
      final type = edge['type'] as String? ?? 'fork';
      final color = switch (type) {
        'merge' => const Color(0xFF8A70C5),
        'evolve' => const Color(0xFF4F9B83),
        'inspired' => colors.tertiary,
        _ => const Color(0xFF4C8DCE),
      };
      final paint = Paint()
        ..color = color.withValues(alpha: 0.8)
        ..strokeWidth = type == 'inspired' ? 1.5 : 2
        ..style = PaintingStyle.stroke;
      if (type == 'inspired') {
        paint.strokeCap = StrokeCap.round;
        const dash = 7.0;
        const gap = 5.0;
        final distance = (target - source).distance;
        final direction = (target - source) / distance;
        for (double offset = 0; offset < distance; offset += dash + gap) {
          final end = math.min(offset + dash, distance).toDouble();
          canvas.drawLine(source + direction * offset, source + direction * end, paint);
        }
      } else {
        canvas.drawLine(source, target, paint);
      }
      final label = switch (type) {
        'merge' => 'Collide',
        'evolve' => 'Evolve',
        'inspired' => 'Inspired',
        _ => 'Fork',
      };
      final painter = TextPainter(
        text: TextSpan(
          text: label,
          style: TextStyle(
            color: color,
            fontSize: 11,
            fontWeight: FontWeight.w600,
            backgroundColor: colors.surface,
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final midpoint = Offset((source.dx + target.dx) / 2, (source.dy + target.dy) / 2);
      painter.paint(canvas, midpoint + const Offset(5, -10));
    }
  }

  @override
  bool shouldRepaint(covariant _UniverseEdgePainter oldDelegate) =>
      oldDelegate.edges != edges ||
      oldDelegate.positions != positions ||
      oldDelegate.colors != colors;
}
