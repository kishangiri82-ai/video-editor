import 'dart:async'; import 'dart:convert'; import 'dart:io';
import 'package:flutter/material.dart'; import 'package:gal/gal.dart'; import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart'; import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart'; import 'package:video_player/video_player.dart';

// SET THESE (or pass with --dart-define)
const base = String.fromEnvironment('API', defaultValue: 'https://YOUR-BACKEND-URL');
const key = String.fromEnvironment('KEY', defaultValue: 'change-me');
final H = {'x-api-key': key};

void main() => runApp(MaterialApp(debugShowCheckedModeBanner: false, theme: ThemeData.dark(useMaterial3: true).copyWith(
    colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepOrange, brightness: Brightness.dark)), home: const Home()));

class Home extends StatefulWidget { const Home({super.key}); @override State<Home> createState() => _S(); }
class _S extends State<Home> {
  List<XFile> media = []; String stage = ''; double prog = 0; String? jid; String aspect = 'Auto'; String quality = '1080p';
  String? err, music; File? local; VideoPlayerController? vc; bool busy = false; String? pid;

  Future pick() async { final m = await ImagePicker().pickMultipleMedia(); if (m.isNotEmpty) setState(() => media = m); }

  Future go({String? avoid}) async {
    setState(() { busy = true; err = null; vc?.dispose(); vc = null; });
    try {
      if (pid == null || avoid == null) {
        pid = jsonDecode((await http.post(Uri.parse('$base/projects'), headers: H)).body)['id'];
        for (var i = 0; i < media.length; i++) {
          setState(() { stage = 'Uploading ${i + 1}/${media.length}'; prog = i / media.length; });
          final r = http.MultipartRequest('POST', Uri.parse('$base/projects/$pid/media'))..headers.addAll(H)
            ..files.add(await http.MultipartFile.fromPath('file', media[i].path, filename: media[i].name));
          final res = await r.send(); if (res.statusCode != 200) throw 'Upload failed: ${media[i].name}';
        }
      }
      final body = {'quality': quality, if (aspect != 'Auto') 'aspect': aspect, if (avoid != null) 'avoid_music': avoid};
      jid = jsonDecode((await http.post(Uri.parse('$base/projects/$pid/render'), headers: {...H, 'content-type': 'application/json'},
          body: jsonEncode(body))).body)['job'];
      while (true) {
        await Future.delayed(const Duration(seconds: 2));
        final j = jsonDecode((await http.get(Uri.parse('$base/jobs/$jid'), headers: H)).body);
        setState(() { stage = j['stage'] ?? ''; prog = (j['progress'] ?? 0).toDouble(); music = j['music']; });
        if (j['status'] == 'error') throw j['error']; if (j['status'] == 'done') break;
      }
      final bytes = (await http.get(Uri.parse('$base/jobs/$jid/video?k=$key'))).bodyBytes;
      final f = File('${(await getTemporaryDirectory()).path}/vlog_$jid.mp4')..writeAsBytesSync(bytes);
      vc = VideoPlayerController.file(f); await vc!.initialize(); vc!.play(); local = f;
    } catch (e) { err = '$e'; }
    setState(() => busy = false);
  }

  @override Widget build(BuildContext c) => Scaffold(appBar: AppBar(title: const Text('AI Auto Video Editor')),
    body: Padding(padding: const EdgeInsets.all(16), child: ListView(children: [
      if (vc != null) ...[AspectRatio(aspectRatio: vc!.value.aspectRatio, child: VideoPlayer(vc!)),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          IconButton(icon: const Icon(Icons.play_arrow), onPressed: () => vc!.value.isPlaying ? vc!.pause() : vc!.play()),
          IconButton(icon: const Icon(Icons.save_alt), onPressed: () async { await Gal.putVideo(local!.path); if (c.mounted) ScaffoldMessenger.of(c).showSnackBar(const SnackBar(content: Text('Saved to gallery'))); }),
          IconButton(icon: const Icon(Icons.share), onPressed: () => Share.shareXFiles([XFile(local!.path)])),
          IconButton(icon: const Icon(Icons.refresh), tooltip: 'Regenerate', onPressed: busy ? null : () => go()),
          IconButton(icon: const Icon(Icons.music_note), tooltip: 'Different music', onPressed: busy ? null : () => go(avoid: music)),
        ])],
      Wrap(spacing: 8, children: [for (final a in ['Auto', '9:16', '16:9', '1:1']) ChoiceChip(label: Text(a), selected: aspect == a, onSelected: (_) => setState(() => aspect = a)),
        for (final q in ['1080p', '720p']) ChoiceChip(label: Text(q), selected: quality == q, onSelected: (_) => setState(() => quality = q))]),
      const SizedBox(height: 12),
      OutlinedButton.icon(onPressed: busy ? null : pick, icon: const Icon(Icons.add_photo_alternate), label: Text('Select videos & photos (${media.length})')),
      SizedBox(height: 90, child: ListView(scrollDirection: Axis.horizontal, children: [for (final m in media) Stack(children: [
        Padding(padding: const EdgeInsets.all(4), child: m.mimeType?.startsWith('video') ?? m.name.toLowerCase().endsWith('.mp4') ? const SizedBox(width: 80, child: Icon(Icons.movie, size: 40)) : Image.file(File(m.path), width: 80, fit: BoxFit.cover)),
        Positioned(right: 0, child: GestureDetector(onTap: () => setState(() => media.remove(m)), child: const Icon(Icons.cancel, size: 20)))])])),
      const SizedBox(height: 12),
      FilledButton(onPressed: busy || media.isEmpty ? null : () => go(), child: const Padding(padding: EdgeInsets.all(14), child: Text('Create My Video Automatically'))),
      if (busy) ...[const SizedBox(height: 16), LinearProgressIndicator(value: prog), Text(stage)],
      if (err != null) Text(err!, style: const TextStyle(color: Colors.redAccent)),
    ])));
}
