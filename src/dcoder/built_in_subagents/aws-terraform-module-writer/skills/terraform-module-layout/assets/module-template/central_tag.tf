// ============================================================
// central_tag.tf — Central tagging module invocation
// ============================================================
// Pattern: Invoke a centralized tagging module for each resource
// using for_each over a tagging map built in locals.tf.
// ============================================================

module "tagging" {
  for_each      = local.tagging_map
  source        = "path/to/centralized-tagging-module"
  standard_tags = each.value["standard_tags"]
}

// The output of this module (e.g., module.tagging[each.key].output_tags)
// is used in the `tags` argument of all taggable resources.
