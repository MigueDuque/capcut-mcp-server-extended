// Utility to publish a VectCutAPI draft into the CapCut drafts directory.
//
// The VectCutAPI stores drafts in its own working directory (VECTCUT_DRAFT_DIR)
// as `draft_info.json`. CapCut expects `draft_content.json` inside a subfolder
// registered in `root_meta_info.json`. This module bridges that gap.

import { promises as fs } from 'fs';
import path from 'path';

export interface PublishDraftParams {
  draftId: string;         // e.g. "dfd_cat_1773623586_80ce38b4"
  vectcutDraftDir: string; // root dir where VectCutAPI keeps drafts
  capcutDraftFolder: string; // CapCut "com.lveditor.draft" root
  draftName: string;       // human-readable name shown in CapCut
  durationSec: number;     // total video duration in seconds
}

// Recursively copy a directory.
async function copyDir(src: string, dest: string): Promise<void> {
  await fs.mkdir(dest, { recursive: true });
  const entries = await fs.readdir(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      await copyDir(srcPath, destPath);
    } else {
      await fs.copyFile(srcPath, destPath);
    }
  }
}

// Convert a forward-slash path to backslash (CapCut stores Windows paths).
function toWin(p: string): string {
  return p.replace(/\//g, '\\');
}

export async function publishDraftToCapcut(params: PublishDraftParams): Promise<string> {
  const { draftId, vectcutDraftDir, capcutDraftFolder, draftName, durationSec } = params;

  const srcDir  = path.join(vectcutDraftDir, draftId);
  const destDir = path.join(capcutDraftFolder, draftId);

  // 1. Copy draft folder from VectCutAPI dir to CapCut drafts dir
  await copyDir(srcDir, destDir);

  // 2. Rename draft_info.json → draft_content.json
  const draftInfoPath    = path.join(destDir, 'draft_info.json');
  const draftContentPath = path.join(destDir, 'draft_content.json');
  try {
    await fs.rename(draftInfoPath, draftContentPath);
  } catch {
    // draft_content.json might already exist if save was called before — that's fine
  }

  // 3. Update draft_meta_info.json with correct local paths
  const metaPath = path.join(destDir, 'draft_meta_info.json');
  const meta = JSON.parse(await fs.readFile(metaPath, 'utf-8'));
  const nowUs = Date.now() * 1000;

  meta.draft_fold_path  = toWin(destDir);
  meta.draft_root_path  = toWin(capcutDraftFolder);
  meta.draft_name       = draftName;
  meta.tm_draft_modified = nowUs;
  meta.tm_duration      = Math.round(durationSec * 1_000_000);

  await fs.writeFile(metaPath, JSON.stringify(meta), 'utf-8');

  // 4. Register draft in root_meta_info.json (idempotent: remove stale entry first)
  const rootPath = path.join(capcutDraftFolder, 'root_meta_info.json');
  const root = JSON.parse(await fs.readFile(rootPath, 'utf-8'));

  const winDestDir = toWin(destDir);
  root.all_draft_store = (root.all_draft_store as unknown[]).filter(
    (e: unknown) => (e as Record<string, string>).draft_fold_path !== winDestDir
  );

  root.all_draft_store.unshift({
    draft_cloud_last_action_download: false,
    draft_cloud_purchase_info: '',
    draft_cloud_template_id: '',
    draft_cloud_tutorial_info: '',
    draft_cloud_videocut_purchase_info: '',
    draft_cover:     `${winDestDir}\\draft_cover.jpg`,
    draft_fold_path: winDestDir,
    draft_id:        meta.draft_id as string,
    draft_is_ai_shorts: false,
    draft_is_invisible: false,
    draft_json_file: `${winDestDir}\\draft_content.json`,
    draft_name:      draftName,
    draft_new_version: '',
    draft_root_path: toWin(capcutDraftFolder),
    draft_timeline_materials_size: 0,
    draft_type: '',
    tm_draft_cloud_completed: '',
    tm_draft_cloud_modified: 0,
    tm_draft_create:   nowUs,
    tm_draft_modified: nowUs,
    tm_draft_removed:  0,
    tm_duration:       Math.round(durationSec * 1_000_000),
  });

  root.draft_ids = (root.all_draft_store as unknown[]).length;
  await fs.writeFile(rootPath, JSON.stringify(root), 'utf-8');

  return destDir;
}
