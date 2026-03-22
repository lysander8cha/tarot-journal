import { useEffect, useRef } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Underline from '@tiptap/extension-underline';
import TextAlign from '@tiptap/extension-text-align';
import './RichTextEditor.css';

interface RichTextEditorProps {
  content: string;
  onChange: (html: string) => void;
  placeholder?: string;
  minHeight?: number;
}

export default function RichTextEditor({
  content,
  onChange,
  placeholder,
  minHeight = 120,
}: RichTextEditorProps) {
  // Track whether the last content change came from the user typing (internal)
  // vs the parent passing new content (external), to avoid update loops.
  const isInternalChange = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Disable heading since journal entries don't need it
        heading: false,
        // Disable code/codeBlock since they're not relevant
        code: false,
        codeBlock: false,
        horizontalRule: false,
      }),
      Underline,
      TextAlign.configure({
        types: ['paragraph'],
      }),
    ],
    content,
    onUpdate: ({ editor }) => {
      isInternalChange.current = true;
      onChange(editor.getHTML());
    },
  });

  // Sync editor content when the prop changes externally (e.g. navigating between cards)
  useEffect(() => {
    if (!editor) return;
    // Skip if this change originated from the user typing in the editor
    if (isInternalChange.current) {
      isInternalChange.current = false;
      return;
    }
    // Only update if the editor's content actually differs from the prop
    if (editor.getHTML() !== content) {
      editor.commands.setContent(content);
    }
  }, [content, editor]);

  if (!editor) return null;

  return (
    <div className="rte">
      <div className="rte__toolbar">
        <div className="rte__group">
          <button
            type="button"
            className={`rte__btn ${editor.isActive('bold') ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().toggleBold().run()}
            title="Bold"
          >
            <strong>B</strong>
          </button>
          <button
            type="button"
            className={`rte__btn ${editor.isActive('italic') ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().toggleItalic().run()}
            title="Italic"
          >
            <em>I</em>
          </button>
          <button
            type="button"
            className={`rte__btn ${editor.isActive('underline') ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().toggleUnderline().run()}
            title="Underline"
          >
            <u>U</u>
          </button>
        </div>

        <div className="rte__separator" />

        <div className="rte__group">
          <button
            type="button"
            className={`rte__btn ${editor.isActive({ textAlign: 'left' }) ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().setTextAlign('left').run()}
            title="Align left"
          >
            &#9776;
          </button>
          <button
            type="button"
            className={`rte__btn ${editor.isActive({ textAlign: 'center' }) ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().setTextAlign('center').run()}
            title="Align center"
          >
            &#9868;
          </button>
          <button
            type="button"
            className={`rte__btn ${editor.isActive({ textAlign: 'right' }) ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().setTextAlign('right').run()}
            title="Align right"
          >
            &#9782;
          </button>
        </div>

        <div className="rte__separator" />

        <div className="rte__group">
          <button
            type="button"
            className={`rte__btn ${editor.isActive('bulletList') ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            title="Bullet list"
          >
            &#8226;
          </button>
          <button
            type="button"
            className={`rte__btn ${editor.isActive('orderedList') ? 'rte__btn--active' : ''}`}
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            title="Numbered list"
          >
            1.
          </button>
        </div>
      </div>

      <div
        className="rte__content"
        style={{ minHeight }}
        data-placeholder={placeholder}
        onClick={() => editor.chain().focus().run()}
      >
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
