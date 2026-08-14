#!/usr/bin/env python3
"""
contract_review_trackchanges_v4.py — V4 refactor of the track-changes script.

Accepts a JSON change list as input (via --changes argument or stdin)
and produces a docx with Word native track-changes (insertions, deletions,
comments). The model produces the JSON change list; this script does the
deterministic docx transformation. The model never directly writes docx bytes.

Usage:
  python contract_review_trackchanges_v4.py --input <input.docx> --changes <changes.json> --output <output.docx>
  python contract_review_trackchanges_v4.py --input <input.docx> --output <output.docx> < changes.json
"""

import zipfile
import os
import sys
import json
import copy
from datetime import datetime, timedelta
from lxml import etree

# OOXML namespaces
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
    'pr': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

W = NS['w']
REVIEWER = "墨律律师审查"
REVIEWER_INITIALS = "墨审"


class TrackChangesBuilder:
    """Builds a docx with Word native track-changes from a change list."""

    def __init__(self, docx_path):
        self.docx_path = docx_path
        with zipfile.ZipFile(docx_path) as z:
            self.files = {name: z.read(name) for name in z.namelist()}

        self.doc_tree = etree.fromstring(self.files['word/document.xml'])
        self.ns_map = NS

        self._next_id = 1000
        self._comment_id = 0
        self.comments = []

        if 'word/settings.xml' in self.files:
            self.settings_tree = etree.fromstring(self.files['word/settings.xml'])
        else:
            self.settings_tree = None

    def _get_next_id(self):
        self._next_id += 1
        return self._next_id

    def _get_comment_id(self):
        cid = self._comment_id
        self._comment_id += 1
        return cid

    def _get_all_paragraph_text(self, p):
        texts = p.findall(f'.//{{{W}}}t')
        return ''.join(t.text or '' for t in texts)

    def _find_paragraph_by_text(self, search_text):
        paras = self.doc_tree.findall(f'.//{{{W}}}p')
        for p in paras:
            full_text = self._get_all_paragraph_text(p)
            if search_text in full_text:
                return p
        return None

    def _create_run_with_text(self, text, rpr=None):
        r = etree.SubElement(etree.Element(f'{{{W}}}placeholder'), f'{{{W}}}r')
        if rpr is not None:
            r.append(copy.deepcopy(rpr))
        t = etree.SubElement(r, f'{{{W}}}t')
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t.text = text
        return r

    def _create_ins_element(self, runs, date=None):
        if date is None:
            date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        ins = etree.Element(f'{{{W}}}ins')
        ins.set(f'{{{W}}}id', str(self._get_next_id()))
        ins.set(f'{{{W}}}author', REVIEWER)
        ins.set(f'{{{W}}}date', date)
        for run in runs:
            ins.append(run)
        return ins

    def _create_del_element(self, run, date=None):
        if date is None:
            date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')
        del_elem = etree.Element(f'{{{W}}}del')
        del_elem.set(f'{{{W}}}id', str(self._get_next_id()))
        del_elem.set(f'{{{W}}}author', REVIEWER)
        del_elem.set(f'{{{W}}}date', date)
        for t in run.findall(f'{{{W}}}t'):
            del_text = etree.SubElement(run, f'{{{W}}}delText')
            del_text.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            del_text.text = t.text
            run.remove(t)
        del_elem.append(run)
        return del_elem

    def _add_comment_to_paragraph(self, p, comment_text, comment_id):
        range_start = etree.Element(f'{{{W}}}commentRangeStart')
        range_start.set(f'{{{W}}}id', str(comment_id))
        p.insert(0, range_start)

        range_end = etree.Element(f'{{{W}}}commentRangeEnd')
        range_end.set(f'{{{W}}}id', str(comment_id))
        p.append(range_end)

        ref_run = etree.Element(f'{{{W}}}r')
        rpr = etree.SubElement(ref_run, f'{{{W}}}rPr')
        rstyle = etree.SubElement(rpr, f'{{{W}}}rStyle')
        rstyle.set(f'{{{W}}}val', 'CommentReference')
        comment_ref = etree.SubElement(ref_run, f'{{{W}}}commentReference')
        comment_ref.set(f'{{{W}}}id', str(comment_id))
        p.append(ref_run)

        self.comments.append({
            'id': comment_id,
            'author': REVIEWER,
            'date': datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ'),
            'text': comment_text,
        })

    def _replace_text_in_paragraph(self, p, old_text, new_text, date=None):
        if date is None:
            date = datetime.now().strftime('%Y-%m-%dT%H:%M:%SZ')

        runs = p.findall(f'{{{W}}}r')
        if not runs:
            return False

        full_text = ""
        run_info = []
        for r in runs:
            t_elems = r.findall(f'{{{W}}}t')
            run_text = ''.join(t.text or '' for t in t_elems)
            start = len(full_text)
            full_text += run_text
            end = len(full_text)
            run_info.append((r, start, end, run_text))

        pos = full_text.find(old_text)
        if pos == -1:
            return False

        old_end = pos + len(old_text)
        new_elements = []

        for r, start, end, run_text in run_info:
            if end <= pos or start >= old_end:
                new_elements.append(r)
            elif start >= pos and end <= old_end:
                del_elem = self._create_del_element(copy.deepcopy(r), date)
                new_elements.append(del_elem)
            elif start < pos and end > old_end:
                before_text = run_text[:pos - start]
                old_part = run_text[pos - start:old_end - start]
                after_text = run_text[old_end - start:]
                rpr = r.find(f'{{{W}}}rPr')
                if before_text:
                    new_elements.append(self._create_run_with_text(before_text, rpr))
                old_run = self._create_run_with_text(old_part, rpr)
                new_elements.append(self._create_del_element(old_run, date))
                if new_text:
                    new_run = self._create_run_with_text(new_text, rpr)
                    new_elements.append(self._create_ins_element([new_run], date))
                if after_text:
                    new_elements.append(self._create_run_with_text(after_text, rpr))
            elif start < pos and end <= old_end:
                before_text = run_text[:pos - start]
                old_part = run_text[pos - start:]
                rpr = r.find(f'{{{W}}}rPr')
                if before_text:
                    new_elements.append(self._create_run_with_text(before_text, rpr))
                old_run = self._create_run_with_text(old_part, rpr)
                new_elements.append(self._create_del_element(old_run, date))
            elif start >= pos and end > old_end:
                old_part = run_text[:old_end - start]
                after_text = run_text[old_end - start:]
                rpr = r.find(f'{{{W}}}rPr')
                old_run = self._create_run_with_text(old_part, rpr)
                new_elements.append(self._create_del_element(old_run, date))
                if new_text:
                    new_run = self._create_run_with_text(new_text, rpr)
                    new_elements.append(self._create_ins_element([new_run], date))
                if after_text:
                    new_elements.append(self._create_run_with_text(after_text, rpr))

        to_remove = [child for child in list(p) if child.tag == f'{{{W}}}r']
        for child in to_remove:
            p.remove(child)

        insert_idx = 0
        for i, child in enumerate(list(p)):
            if child.tag == f'{{{W}}}pPr':
                insert_idx = i + 1
                break

        for i, elem in enumerate(new_elements):
            p.insert(insert_idx + i, elem)

        return True

    def _build_comments_xml(self):
        if not self.comments:
            return None
        nsmap = {'w': W}
        root = etree.Element(f'{{{W}}}comments', nsmap=nsmap)
        for c in self.comments:
            comment = etree.SubElement(root, f'{{{W}}}comment')
            comment.set(f'{{{W}}}id', str(c['id']))
            comment.set(f'{{{W}}}author', c['author'])
            comment.set(f'{{{W}}}date', c['date'])
            comment.set(f'{{{W}}}initials', REVIEWER_INITIALS)
            p = etree.SubElement(comment, f'{{{W}}}p')
            r = etree.SubElement(p, f'{{{W}}}r')
            t = etree.SubElement(r, f'{{{W}}}t')
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            t.text = c['text']
        return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)

    def _update_content_types(self, content_types_xml):
        ct_tree = etree.fromstring(content_types_xml)
        ct_ns = 'http://schemas.openxmlformats.org/package/2006/content-types'
        has_comments = False
        for override in ct_tree.findall(f'{{{ct_ns}}}Override'):
            if override.get('PartName') == '/word/comments.xml':
                has_comments = True
                break
        if not has_comments and self.comments:
            override = etree.SubElement(ct_tree, f'{{{ct_ns}}}Override')
            override.set('PartName', '/word/comments.xml')
            override.set('ContentType', 'application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml')
        return etree.tostring(ct_tree, xml_declaration=True, encoding='UTF-8', standalone=True)

    def _update_rels(self, rels_xml):
        rels_tree = etree.fromstring(rels_xml)
        rel_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
        has_comments_rel = False
        max_id = 0
        for rel in rels_tree.findall(f'{{{rel_ns}}}Relationship'):
            rid = rel.get('Id', '')
            if rid.startswith('rId'):
                try:
                    num = int(rid[3:])
                    if num > max_id:
                        max_id = num
                except ValueError:
                    pass
            if rel.get('Target') == 'comments.xml':
                has_comments_rel = True
        if not has_comments_rel and self.comments:
            rel = etree.SubElement(rels_tree, f'{{{rel_ns}}}Relationship')
            rel.set('Id', f'rId{max_id + 1}')
            rel.set('Type', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments')
            rel.set('Target', 'comments.xml')
        return etree.tostring(rels_tree, xml_declaration=True, encoding='UTF-8', standalone=True)

    def _ensure_comment_style(self):
        if 'word/styles.xml' not in self.files:
            return
        styles_tree = etree.fromstring(self.files['word/styles.xml'])
        has_style = False
        for style in styles_tree.findall(f'{{{W}}}style'):
            if style.get(f'{{{W}}}styleId') == 'CommentReference':
                has_style = True
                break
        if not has_style:
            style = etree.SubElement(styles_tree, f'{{{W}}}style')
            style.set(f'{{{W}}}type', 'character')
            style.set(f'{{{W}}}styleId', 'CommentReference')
            name = etree.SubElement(style, f'{{{W}}}name')
            name.set(f'{{{W}}}val', 'annotation reference')
        self.files['word/styles.xml'] = etree.tostring(styles_tree, xml_declaration=True, encoding='UTF-8', standalone=True)

    def process(self, change_items):
        """Process change items from the JSON change list."""
        results = []
        base_date = datetime.now()

        for item in change_items:
            item_id = item.get('id', 0)
            level = item.get('riskLevel', 'P2')
            find_text = item.get('originalText', '')
            old_text = item.get('originalText', '')
            new_text = item.get('revisedText')
            comment = item.get('comment', '')

            date = (base_date + timedelta(minutes=item_id * 7)).strftime('%Y-%m-%dT%H:%M:%SZ')

            p = self._find_paragraph_by_text(find_text)
            if p is None:
                results.append((item_id, level, 'NOT FOUND', comment[:50]))
                continue

            comment_id = self._get_comment_id()
            self._add_comment_to_paragraph(p, comment, comment_id)

            if old_text and new_text:
                p = self._find_paragraph_by_text(find_text)
                if p:
                    success = self._replace_text_in_paragraph(p, old_text, new_text, date)
                    results.append((item_id, level, 'REPLACED' if success else 'REPLACE FAILED', comment[:50]))
                else:
                    results.append((item_id, level, 'RE-FIND FAILED', comment[:50]))
            else:
                results.append((item_id, level, 'COMMENT ONLY', comment[:50]))

        return results

    def save(self, output_path):
        self._ensure_comment_style()
        self.files['word/document.xml'] = etree.tostring(
            self.doc_tree, xml_declaration=True, encoding='UTF-8', standalone=True
        )
        self.files['[Content_Types].xml'] = self._update_content_types(self.files['[Content_Types].xml'])
        self.files['word/_rels/document.xml.rels'] = self._update_rels(self.files['word/_rels/document.xml.rels'])
        comments_xml = self._build_comments_xml()
        if comments_xml:
            self.files['word/comments.xml'] = comments_xml

        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as z:
            for name, data in self.files.items():
                z.writestr(name, data)

        return output_path


def main():
    import argparse
    parser = argparse.ArgumentParser(description='V4 track-changes docx generator')
    parser.add_argument('--input', required=True, help='Input docx path')
    parser.add_argument('--changes', help='JSON change list file path (or read from stdin)')
    parser.add_argument('--output', required=True, help='Output docx path')
    args = parser.parse_args()

    # Read change list JSON
    if args.changes:
        with open(args.changes, 'r', encoding='utf-8') as f:
            change_data = json.load(f)
    else:
        change_data = json.load(sys.stdin)

    change_items = change_data.get('items', [])

    builder = TrackChangesBuilder(args.input)
    results = builder.process(change_items)
    builder.save(args.output)

    # Output results as JSON to stdout
    output = {
        'outputPath': args.output,
        'totalItems': len(results),
        'results': [
            {'id': r[0], 'level': r[1], 'status': r[2], 'comment': r[3]}
            for r in results
        ],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
