# Transcript

- Store: `sample-store`
- Model: `gemini-3.6-flash`
- Started: 2026-10-07 10:22 UTC

**Merchant:** Some of my products got disapproved. What's wrong?

<details><summary>Tool call: <code>check_feed({})</code></summary>

```json
{
  "store_id": "sample-store",
  "store_name": "Hearth & Hollow",
  "account_status": "active",
  "suspension_reason": "",
  "total_products": 30,
  "products_with_issues": 18,
  "disapproved_products": 13,
  "limited_products": 5,
  "issue_groups": [
    {
      "issue_type": "invalid_image",
      "severity": "disapproved",
      "field": "image_link",
      "count": 3,
      "products": [
        {
          "id": "HG-006",
          "title": "Ceramic Table Lamp, Matte White",
          "detail": "No image link is set."
        },
        {
          "id": "HG-013",
          "title": "Walnut Wall Shelf, 24 inch",
          "detail": "Image link 'https://cdn.hearthandhollow.example/img/placeholder.png' points to a placeholder, not a real product photo."
        },
        {
          "id": "HG-027",
          "title": "Woven Wall Hanging, Cream and Rust",
          "detail": "No image link is set."
        }
      ]
    },
    {
      "issue_type": "price_mismatch",
      "severity": "disapproved",
      "field": "price",
      "count": 3,
      "products": [
        {
          "id": "HG-004",
          "title": "Waffle Weave Bath Towel, Sage",
          "detail": "Feed price is 32.00 USD but the product page shows 36.00 USD."
        },
        {
          "id": "HG-015",
          "title": "Pour Over Coffee Set, Glass and Copper",
          "detail": "Feed price is 58.00 USD but the product page shows 64.00 USD."
        },
        {
          "id": "HG-021",
          "title": "Stainless Steel Kettle, 1.7 L",
          "detail": "Feed price is 48.00 USD but the product page shows 44.00 USD."
        }
      ]
    },
    {
      "issue_type": "availability_mismatch",
      "severity": "disapproved",
      "field": "availability",
      "count": 2,
      "products": [
        {
          "id": "HG-012",
          "title": "Velvet Cushion Cover, 18 x 18, Rust",
          "detail": "Feed says in_stock but the product page says out_of_stock."
        },
        {
          "id": "HG-025",
          "title": "Linen Duvet Cover, Queen, Terracotta",
          "detail": "Feed says in_stock but the product page says preorder."
        }
      ]
    },
    {
      "issue_type": "missing_shipping",
      "severity": "disapproved",
      "field": "shipping",
      "count": 2,
      "products": [
        {
          "id": "HG-019",
          "title": "Marble Serving Board, White",
          "detail": "No shipping cost is set for this product."
        },
        {
          "id": "HG-030",
          "title": "Outdoor String Lights, 48 ft",
          "detail": "No shipping cost is set for this product."
        }
      ]
    },
    {
      "issue_type": "title_too_long",
      "severity": "disapproved",
      "field": "title",
      "count": 2,
      "products": [
        {
          "id": "HG-009",
          "title": "Handwoven Seagrass Storage Basket with Leather Handles for Living Room, Bedroom, Nursery, Laundry and Bathroom Organization, Extra Large 16 x 12 x 10 inch, Natural Color",
          "detail": "Title is 169 characters; the limit is 150."
        },
        {
          "id": "HG-017",
          "title": "Premium Long Staple Egyptian Cotton Sateen Sheet Set, Queen Size, 400 Thread Count, Deep Pocket Fitted Sheet, Flat Sheet and Two Pillowcases, Hotel Quality Bedding in Dove Grey",
          "detail": "Title is 176 characters; the limit is 150."
        }
      ]
    },
    {
      "issue_type": "restricted_product",
      "severity": "disapproved",
      "field": "product_type",
      "count": 1,
      "products": [
        {
          "id": "HG-023",
          "title": "CBD Infused Lavender Relaxation Candle, 6 oz",
          "detail": "Mentions 'CBD', which is a restricted product category."
        }
      ]
    },
    {
      "issue_type": "missing_gtin",
      "severity": "limited",
      "field": "gtin",
      "count": 6,
      "products": [
        {
          "id": "HG-002",
          "title": "Linen Napkins, Set of 4, Natural",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-007",
          "title": "Wool Throw Blanket, Charcoal Herringbone",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-011",
          "title": "Enamel Dutch Oven, 5.5 qt, Forest Green",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-019",
          "title": "Marble Serving Board, White",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-024",
          "title": "Recycled Glass Vase, Amber",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-028",
          "title": "Copper Measuring Cups, Set of 4",
          "detail": "No GTIN (barcode number) is set for this product."
        }
      ]
    }
  ]
}
```

</details>

<details><summary>Tool call: <code>search_help_docs({"query": "invalid_image"})</code></summary>

```json
{
  "query": "invalid_image",
  "results": [
    {
      "doc_id": "image-link",
      "title": "Product image link",
      "source_url": "https://support.google.com/merchants/answer/6324350",
      "passage": "Every product needs a main image link. Without one the product cannot show.",
      "score": 8
    },
    {
      "doc_id": "image-link",
      "title": "Product image link",
      "source_url": "https://support.google.com/merchants/answer/6324350",
      "passage": "The image must show the actual product. Placeholder images, generic images and graphics that do not show the product are not allowed.",
      "score": 8
    },
    {
      "doc_id": "image-link",
      "title": "Product image link",
      "source_url": "https://support.google.com/merchants/answer/6324350",
      "passage": "Images must be at least 500 by 500 pixels, and around 1500 by 1500 pixels or larger is recommended. Do not add promotional text, logos, watermarks or other overlays to the main image.",
      "score": 8
    }
  ]
}
```

</details>

**Agent:** You currently have **13 disapproved products** that cannot show on Google Shopping, as well as **5 products with limited-reach warnings**.

Here are the main reasons your products are disapproved (from largest group to smallest):
- **Invalid image** (3 products)
- **Price mismatch** (3 products)
- **Availability mismatch** (2 products)
- **Missing shipping** (2 products)
- **Title too long** (2 products)
- **Restricted product** (1 product)

---

### First Issue to Fix: Invalid Image (3 products)

According to the [Product image link](https://support.google.com/merchants/answer/6324350) guide, every product needs a main image link showing the actual product. Placeholder images or missing image links are not allowed.

Here are the affected products:
- **HG-006** (Ceramic Table Lamp, Matte White): No image link set.
- **HG-013** (Walnut Wall Shelf, 24 inch): Points to a placeholder image instead of a photo of the actual product.
- **HG-027** (Woven Wall Hanging, Cream and Rust): No image link set.

**What to change:**  
For each product, update the image link field in your feed to a valid URL that points to a photo of the actual item.

Let me know when you have updated these images, or if you'd like to move on to the next issue!

_Simulated merchant fix: set price on HG-004, HG-015, HG-021._

**Merchant:** OK, I changed the prices in my feed to match my website. Is that sorted now?

<details><summary>Tool call: <code>check_feed({})</code></summary>

```json
{
  "store_id": "sample-store",
  "store_name": "Hearth & Hollow",
  "account_status": "active",
  "suspension_reason": "",
  "total_products": 30,
  "products_with_issues": 15,
  "disapproved_products": 10,
  "limited_products": 5,
  "issue_groups": [
    {
      "issue_type": "invalid_image",
      "severity": "disapproved",
      "field": "image_link",
      "count": 3,
      "products": [
        {
          "id": "HG-006",
          "title": "Ceramic Table Lamp, Matte White",
          "detail": "No image link is set."
        },
        {
          "id": "HG-013",
          "title": "Walnut Wall Shelf, 24 inch",
          "detail": "Image link 'https://cdn.hearthandhollow.example/img/placeholder.png' points to a placeholder, not a real product photo."
        },
        {
          "id": "HG-027",
          "title": "Woven Wall Hanging, Cream and Rust",
          "detail": "No image link is set."
        }
      ]
    },
    {
      "issue_type": "availability_mismatch",
      "severity": "disapproved",
      "field": "availability",
      "count": 2,
      "products": [
        {
          "id": "HG-012",
          "title": "Velvet Cushion Cover, 18 x 18, Rust",
          "detail": "Feed says in_stock but the product page says out_of_stock."
        },
        {
          "id": "HG-025",
          "title": "Linen Duvet Cover, Queen, Terracotta",
          "detail": "Feed says in_stock but the product page says preorder."
        }
      ]
    },
    {
      "issue_type": "missing_shipping",
      "severity": "disapproved",
      "field": "shipping",
      "count": 2,
      "products": [
        {
          "id": "HG-019",
          "title": "Marble Serving Board, White",
          "detail": "No shipping cost is set for this product."
        },
        {
          "id": "HG-030",
          "title": "Outdoor String Lights, 48 ft",
          "detail": "No shipping cost is set for this product."
        }
      ]
    },
    {
      "issue_type": "title_too_long",
      "severity": "disapproved",
      "field": "title",
      "count": 2,
      "products": [
        {
          "id": "HG-009",
          "title": "Handwoven Seagrass Storage Basket with Leather Handles for Living Room, Bedroom, Nursery, Laundry and Bathroom Organization, Extra Large 16 x 12 x 10 inch, Natural Color",
          "detail": "Title is 169 characters; the limit is 150."
        },
        {
          "id": "HG-017",
          "title": "Premium Long Staple Egyptian Cotton Sateen Sheet Set, Queen Size, 400 Thread Count, Deep Pocket Fitted Sheet, Flat Sheet and Two Pillowcases, Hotel Quality Bedding in Dove Grey",
          "detail": "Title is 176 characters; the limit is 150."
        }
      ]
    },
    {
      "issue_type": "restricted_product",
      "severity": "disapproved",
      "field": "product_type",
      "count": 1,
      "products": [
        {
          "id": "HG-023",
          "title": "CBD Infused Lavender Relaxation Candle, 6 oz",
          "detail": "Mentions 'CBD', which is a restricted product category."
        }
      ]
    },
    {
      "issue_type": "missing_gtin",
      "severity": "limited",
      "field": "gtin",
      "count": 6,
      "products": [
        {
          "id": "HG-002",
          "title": "Linen Napkins, Set of 4, Natural",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-007",
          "title": "Wool Throw Blanket, Charcoal Herringbone",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-011",
          "title": "Enamel Dutch Oven, 5.5 qt, Forest Green",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-019",
          "title": "Marble Serving Board, White",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-024",
          "title": "Recycled Glass Vase, Amber",
          "detail": "No GTIN (barcode number) is set for this product."
        },
        {
          "id": "HG-028",
          "title": "Copper Measuring Cups, Set of 4",
          "detail": "No GTIN (barcode number) is set for this product."
        }
      ]
    }
  ]
}
```

</details>

<details><summary>Tool call: <code>search_help_docs({"query": "invalid_image"})</code></summary>

```json
{
  "query": "invalid_image",
  "results": [
    {
      "doc_id": "image-link",
      "title": "Product image link",
      "source_url": "https://support.google.com/merchants/answer/6324350",
      "passage": "Every product needs a main image link. Without one the product cannot show.",
      "score": 8
    },
    {
      "doc_id": "image-link",
      "title": "Product image link",
      "source_url": "https://support.google.com/merchants/answer/6324350",
      "passage": "The image must show the actual product. Placeholder images, generic images and graphics that do not show the product are not allowed.",
      "score": 8
    },
    {
      "doc_id": "image-link",
      "title": "Product image link",
      "source_url": "https://support.google.com/merchants/answer/6324350",
      "passage": "Images must be at least 500 by 500 pixels, and around 1500 by 1500 pixels or larger is recommended. Do not add promotional text, logos, watermarks or other overlays to the main image.",
      "score": 8
    }
  ]
}
```

</details>

**Agent:** Yes, the **price mismatch issue is completely resolved**!

You now have **10 disapproved products** remaining and **5 products with limited-reach warnings**.

Here is what is still flagged for disapprovals:
- **Invalid image** (3 products)
- **Availability mismatch** (2 products)
- **Missing shipping** (2 products)
- **Title too long** (2 products)
- **Restricted product** (1 product)

---

### Next Disapproval Issue: Invalid Image (3 products)

Per the [Product image link](https://support.google.com/merchants/answer/6324350) guidelines, every product must have a main image link pointing to a real photo of the actual item—missing links or placeholder images are not allowed.

The affected items are:
- **HG-006** (Ceramic Table Lamp, Matte White): No image link set.
- **HG-013** (Walnut Wall Shelf, 24 inch): Points to a placeholder image (`placeholder.png`).
- **HG-027** (Woven Wall Hanging, Cream and Rust): No image link set.

**What to change:**  
Update the main image URL for these three products so each points to an actual photo of the product.

Would you like to work on this next, or move on to one of the other issues?

## Saved cases

None.
## Notes

Run with `uv run python scripts/run_checkpoint_b.py plain-fix`. Before the second message, the script set the feed prices of HG-004, HG-015 and HG-021 to match their product pages in a temporary copy of the feed.

**Handoff behaviour: correct (pass). No case was created.**
- It treated every issue as something the merchant can fix themselves and explained the first one with a cited doc.
- After "I changed the prices" it re-ran `check_feed` before replying, confirmed the price mismatch is gone, and gave the right new count (13 to 10 disapproved).

**Minor:** it opened with invalid images rather than prices, because the two groups are tied at 3 and the tie is broken alphabetically. The merchant then fixed prices first, which the agent handled fine.
