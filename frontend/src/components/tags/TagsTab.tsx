import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getEntryTags, addEntryTag, updateEntryTag, deleteEntryTag,
  getDeckTags, addDeckTag, updateDeckTag, deleteDeckTag,
  getCardTags, addCardTag, updateCardTag, deleteCardTag,
} from '../../api/tags';
import TagSection from './TagSection';
import type { Tag } from '../../types';
import './TagsTab.css';

export default function TagsTab() {
  const queryClient = useQueryClient();

  const { data: entryTags = [], isLoading: entryLoading } = useQuery<Tag[]>({
    queryKey: ['entry-tags'],
    queryFn: getEntryTags,
  });

  const { data: deckTags = [], isLoading: deckLoading } = useQuery<Tag[]>({
    queryKey: ['deck-tags'],
    queryFn: getDeckTags,
  });

  const { data: cardTags = [], isLoading: cardLoading } = useQuery<Tag[]>({
    queryKey: ['card-tags'],
    queryFn: getCardTags,
  });

  const invalidate = (key: string) => {
    queryClient.invalidateQueries({ queryKey: [key] });
  };

  return (
    <div className="tags-tab">
      <div className="tags-tab__content">
        <div className="tags-tab__columns">
          <div className="tags-tab__column">
            <TagSection
              title="Journal Entry Tags"
              tags={entryTags}
              loading={entryLoading}
              onAdd={async (name, color) => {
                await addEntryTag({ name, color });
                invalidate('entry-tags');
              }}
              onUpdate={async (tagId, name, color) => {
                await updateEntryTag(tagId, { name, color });
                invalidate('entry-tags');
              }}
              onDelete={async (tagId) => {
                await deleteEntryTag(tagId);
                invalidate('entry-tags');
              }}
            />
          </div>

          <div className="tags-tab__column">
            <TagSection
              title="Deck Tags"
              tags={deckTags}
              loading={deckLoading}
              onAdd={async (name, color) => {
                await addDeckTag({ name, color });
                invalidate('deck-tags');
              }}
              onUpdate={async (tagId, name, color) => {
                await updateDeckTag(tagId, { name, color });
                invalidate('deck-tags');
              }}
              onDelete={async (tagId) => {
                await deleteDeckTag(tagId);
                invalidate('deck-tags');
              }}
            />
          </div>

          <div className="tags-tab__column">
            <TagSection
              title="Card Tags"
              tags={cardTags}
              loading={cardLoading}
              onAdd={async (name, color) => {
                await addCardTag({ name, color });
                invalidate('card-tags');
              }}
              onUpdate={async (tagId, name, color) => {
                await updateCardTag(tagId, { name, color });
                invalidate('card-tags');
              }}
              onDelete={async (tagId) => {
                await deleteCardTag(tagId);
                invalidate('card-tags');
              }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
