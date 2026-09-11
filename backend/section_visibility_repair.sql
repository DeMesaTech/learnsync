-- One-time repair for module/activity section links created before lookups
-- were limited to the content item's own class.
-- Review and run this against the LearnSync PostgreSQL database once.

UPDATE activity_sections AS link
SET section_id = correct_section.section_id
FROM activity AS activity_item,
     section AS linked_section,
     section AS correct_section
WHERE link.activity_id = activity_item.activity_id
  AND linked_section.section_id = link.section_id
  AND linked_section.class_id IS DISTINCT FROM activity_item.class_id
  AND correct_section.class_id = activity_item.class_id
  AND correct_section.section = linked_section.section;

UPDATE module_sections AS link
SET section_id = correct_section.section_id
FROM module AS module_item,
     section AS linked_section,
     section AS correct_section
WHERE link.module_id = module_item.module_id
  AND linked_section.section_id = link.section_id
  AND linked_section.class_id IS DISTINCT FROM module_item.class_id
  AND correct_section.class_id = module_item.class_id
  AND correct_section.section = linked_section.section;
