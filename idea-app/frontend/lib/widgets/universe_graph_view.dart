import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import 'force_layout.dart';

class UniverseGraphView extends StatefulWidget {
  final Map<String, dynamic> graph;
  final ValueChanged<String>? onNodeTap;

  const UniverseGraphView({
    super.key,
    required this.graph,
    this.onNodeTap,
  });

  @override
  State<UniverseGraphView> createState() => _UniverseGraphViewState();
}

class _UniverseGraphViewState extends State<UniverseGraphView>
    with SingleTickerProviderStateMixin {
  static const double _canvasSize = 960;
  late final Ticker _ticker;
  ForceSimulation? _simulation;
  Map<String, ForceNode> _nodeMap = {};
  List<Map<String, dynamic>> _edges = [];

  @override
  void initState() {
    super.initState();
    _ticker = createTicker((_) {
      final simulation = _simulation;
      if (simulation == null) return;
      if (simulation.isStable()) {
        _ticker.stop();
        return;
      }
      simulation.tick();
      if (mounted) setState(() {});
    });
    _initialize();
  }

  @override
  void didUpdateWidget(covariant UniverseGraphView oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.graph != widget.graph) _initialize();
  }

  void _initialize() {
    _ticker.stop();
    final rawNodes = (widget.graph['nodes'] as List<dynamic>? ?? [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    _edges = (widget.graph['edges'] as List<dynamic>? ?? [])
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();

    final grouped = <int, List<Map<String, dynamic>>>{};
    for (final node in rawNodes) {
      if (node['is_root'] == true) continue;
      final depth = node['depth'] as int? ?? 1;
      grouped.putIfAbsent(depth, () => []).add(node);
    }

    final nodes = <ForceNode>[];
    _nodeMap = {};
    final center = const Offset(_canvasSize / 2, _canvasSize / 2);
    final rootData = rawNodes.firstWhere(
      (node) => node['is_root'] == true,
      orElse: () => rawNodes.isEmpty ? <String, dynamic>{} : rawNodes.first,
    );
    final rootId = rootData['id'] as String? ?? '';
    for (final entry in grouped.entries) {
      final items = entry.value;
      for (var i = 0; i < items.length; i++) {
        final angle = (2 * math.pi * i / math.max(1, items.length)) - math.pi / 2;
        final radius = 150.0 + entry.key * 110.0;
        final id = items[i]['id'] as String;
        final node = ForceNode(
          key: id,
          data: items[i],
          position: center + Offset(math.cos(angle) * radius, math.sin(angle) * radius),
          radius: items[i]['node_type'] == 'restricted' ? 18 : 23,
        );
        nodes.add(node);
        _nodeMap[id] = node;
      }
    }

    final root = ForceNode(
      key: rootId,
      data: rootData,
      position: center,
      fixed: true,
      radius: 31,
    );
    nodes.insert(0, root);
    _nodeMap[rootId] = root;

    final links = <ForceLink>[];
    for (final edge in _edges) {
      final source = _nodeMap[edge['source']];
      final target = _nodeMap[edge['target']];
      if (source == null || target == null) continue;
      links.add(ForceLink(source: source, target: target, distance: 135));
    }

    _simulation = ForceSimulation(
      nodes: nodes,
      links: links,
      forces: [
        ChargeForce(strength: -900),
        LinkForce(strength: 0.28),
        CenterForce(center: center),
        CollideForce(),
      ],
      alphaDecay: 0.035,
      velocityDecay: 0.52,
    );
    if (nodes.length > 1) _ticker.start();
  }

  void _handleTap(TapUpDetails details) {
    final point = details.localPosition;
    for (final node in _nodeMap.values) {
      final data = node.data;
      if (data['navigable'] != true) continue;
      if ((node.position - point).distance <= node.radius + 8) {
        final id = node.key;
        if (id != widget.graph['root_id']) widget.onNodeTap?.call(id);
        return;
      }
    }
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final textColor = Theme.of(context).colorScheme.onSurface;
    return ClipRect(
      child: InteractiveViewer(
        minScale: 0.35,
        maxScale: 2.5,
        constrained: false,
        boundaryMargin: const EdgeInsets.all(240),
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onTapUp: _handleTap,
          child: SizedBox(
            width: _canvasSize,
            height: _canvasSize,
            child: CustomPaint(
              painter: _UniversePainter(
                nodes: _nodeMap.values.toList(),
                edges: _edges,
                textColor: textColor,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _UniversePainter extends CustomPainter {
  final List<ForceNode> nodes;
  final List<Map<String, dynamic>> edges;
  final Color textColor;

  _UniversePainter({
    required this.nodes,
    required this.edges,
    required this.textColor,
  });

  Color _edgeColor(String type) {
    switch (type) {
      case 'fork':
        return const Color(0xFF2A9D8F);
      case 'merge':
        return const Color(0xFF7B61A8);
      case 'evolve':
        return const Color(0xFFE09F3E);
      case 'inspired':
        return const Color(0xFFD65A8A);
      default:
        return Colors.blueGrey;
    }
  }

  Color _nodeColor(Map<String, dynamic> data) {
    if (data['node_type'] == 'restricted') return const Color(0xFF9CA3AF);
    final value = (data['color_hex'] as String? ?? '#6B7280').replaceFirst('#', '');
    try {
      return Color(int.parse('FF$value', radix: 16));
    } catch (_) {
      return const Color(0xFF6B7280);
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    final byId = {for (final node in nodes) node.key: node};
    for (final edge in edges) {
      final source = byId[edge['source']];
      final target = byId[edge['target']];
      if (source == null || target == null) continue;
      final color = _edgeColor(edge['type'] as String? ?? '');
      final paint = Paint()
        ..color = color.withOpacity(0.82)
        ..strokeWidth = edge['type'] == 'inspired' ? 2.2 : 2.8
        ..style = PaintingStyle.stroke;
      final start = source.position;
      final end = target.position;
      if (edge['type'] == 'inspired') {
        final distance = (end - start).distance;
        final direction = (end - start) / math.max(distance, 0.01);
        var cursor = 0.0;
        while (cursor < distance - 18) {
          final finish = math.min(cursor + 9, distance - 18).toDouble();
          canvas.drawLine(start + direction * cursor, start + direction * finish, paint);
          cursor += 15;
        }
      } else {
        canvas.drawLine(start, end, paint);
      }
      final delta = end - start;
      final length = math.max(delta.distance, 0.01).toDouble();
      final unit = delta / length;
      final tip = end - unit * target.radius;
      final perpendicular = Offset(-unit.dy, unit.dx);
      final arrow = Path()
        ..moveTo(tip.dx, tip.dy)
        ..lineTo(tip.dx - unit.dx * 10 + perpendicular.dx * 5,
            tip.dy - unit.dy * 10 + perpendicular.dy * 5)
        ..lineTo(tip.dx - unit.dx * 10 - perpendicular.dx * 5,
            tip.dy - unit.dy * 10 - perpendicular.dy * 5)
        ..close();
      canvas.drawPath(arrow, Paint()..color = color);
    }

    for (final node in nodes) {
      final data = node.data;
      final color = _nodeColor(data);
      final isRoot = data['is_root'] == true;
      final fill = Paint()..color = color.withOpacity(0.18);
      final stroke = Paint()
        ..color = isRoot ? const Color(0xFFC79A36) : color
        ..strokeWidth = isRoot ? 4 : 2.4
        ..style = PaintingStyle.stroke;
      canvas.drawCircle(node.position, node.radius, fill);
      canvas.drawCircle(node.position, node.radius, stroke);
      if (data['node_type'] == 'restricted') {
        final lockPaint = Paint()
          ..color = color
          ..strokeWidth = 2
          ..style = PaintingStyle.stroke;
        final rect = Rect.fromCenter(
          center: node.position,
          width: 12,
          height: 10,
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(rect, const Radius.circular(2)),
          lockPaint,
        );
        canvas.drawArc(
          Rect.fromCenter(center: node.position.translate(0, -5), width: 8, height: 9),
          math.pi,
          math.pi,
          false,
          lockPaint,
        );
      } else {
        final dot = Paint()..color = color;
        canvas.drawCircle(node.position, isRoot ? 8 : 6, dot);
      }

      final title = (data['title'] as String? ?? '').trim();
      final painter = TextPainter(
        text: TextSpan(
          text: title.isEmpty ? '未命名创意' : title,
          style: TextStyle(
            color: textColor,
            fontSize: isRoot ? 15 : 12,
            fontWeight: isRoot ? FontWeight.w700 : FontWeight.w500,
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 2,
        ellipsis: '…',
      )..layout(maxWidth: 116);
      painter.paint(
        canvas,
        Offset(node.position.dx - painter.width / 2, node.position.dy + node.radius + 7),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _UniversePainter oldDelegate) => true;
}
