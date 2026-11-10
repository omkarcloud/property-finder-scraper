# 🏠 Property Finder Scraper

Property Finder Scraper is a **free and open-source** scraper that gets you **unlimited** detailed Property Finder real estate data for free.

## ✨ What Can I Get?

- 🏠 **Full details on 390K+ UAE listings** — price, every photo, permit, agent, price trends & similar sales
- 📈 **5.8M+ Dubai sales & rentals** — Dubai Land Department prices, unit numbers, previous prices & rental yields
- 👤 **17K+ agents & 3,900+ companies** — ratings, closed deals, RERA licences, company emails & phones
- 🏗️ **2,900+ new projects from 960 developers** — floor plans, payment plans, handover dates & FAQs

## 🎥 Example: A Full Property Finder Listing

```json
{
  "id": 167877493,
  "link": "https://www.propertyfinder.ae/en/plp/buy/villa-for-sale-dubai-palm-jumeirah-the-crescent-xxii-carat-villas-167877493.html",
  "title": "Ultra-Private Beachfront Estate in XXII Carat",
  "property_type": "Villa",
  "price": { "amount": 290000000, "currency": "AED", "period": null, "is_hidden": false },
  "price_per_sqft": 14250,
  "bedrooms": 7,
  "bathrooms": 9,
  "size": { "value": 20350, "unit": "sqft" },
  "built_up_area": 12124,
  "furnished": "furnished",
  "listed_date": "2026-11-02T08:53:51Z",
  "location": { "id": 16996, "full_name": "XXII Carat Villas, The Crescent, Palm Jumeirah, Dubai", "coordinates": { "lat": 25.0988, "lon": 55.131 } },
  "images_count": 30,
  "images": [
    { "full": "https://static.shared.propertyfinder.ae/media/images/listing/TXGZBGCK8D2HH9M63JSYPEQZK8/2da8af06-1ffe-4d67-b307-20d290f7977c/1312x894.jpg?v=5c08b02f4310931572602019136d1688" }
  ],
  "amenities": [{ "code": "PP", "name": "Private Pool" }, { "code": "VW", "name": "View of Water" }],
  "agent": { "id": 187200, "name": "Stephan Hirzel", "position": "Director", "is_super_agent": true, "languages": ["English", "German"], "years_of_experience": 26 },
  "company": { "id": 1144, "name": "Dubai Sotheby's International Realty", "email": "leads@sothebysrealty.ae", "phone": "+97144550887", "license_number": "12521" },
  "similar_transactions": { "buy": [{ "date": "2025-07-24", "amount": 59800000, "size": 18258 }], "rent": null },
  "price_comparison": { "location_name": "Palm Jumeirah", "average_price": 90420775, "price_difference_pct": 220.72, "is_cheaper": false },
  "mortgage_rate": 3.75
}
```

*Trimmed for readability.*

## 🚀 Unlimited Free Property Finder Data — Get It in 60 Seconds

1️⃣ Clone and install:
```bash
git clone https://github.com/omkarcloud/property-finder-scraper
cd property-finder-scraper
python -m pip install -r requirements.txt
```

2️⃣ Start the API:
```bash
python run.py
```

3️⃣ Get your first data:
```bash
curl "http://localhost:8000/properties/details?property=167877493"
```

```json
{
  "id": 167877493,
  "title": "Ultra-Private Beachfront Estate in XXII Carat",
  "property_type": "Villa",
  "price": { "amount": 290000000, "currency": "AED", "period": null, "is_hidden": false },
  "price_per_sqft": 14250,
  "bedrooms": 7,
  "bathrooms": 9,
  "size": { "value": 20350, "unit": "sqft" },
  "completion_status": "completed",
  "listed_date": "2026-11-02T08:53:51Z",
  "is_verified": true,
  "location": { "name": "XXII Carat Villas", "full_name": "XXII Carat Villas, The Crescent, Palm Jumeirah, Dubai", "coordinates": { "lat": 25.0988, "lon": 55.131 } },
  "images_count": 30,
  "agent": { "id": 187200, "name": "Stephan Hirzel", "is_super_agent": true },
  "company": { "id": 1144, "name": "Dubai Sotheby's International Realty", "phone": "+97144550887", "license_number": "12521" },
  "similar_transactions": { "buy": [{ "date": "2025-07-24", "amount": 59800000, "size": 18258 }], "rent": null }
}
```

All 18 endpoints are now live at `http://localhost:8000`.

## 📚 Endpoints

18 endpoints cover everything you need.

| Endpoint | Path | Returns |
|---|---|---|
| Property Details | `/properties/details` | Everything about one listing: price, photos, permit, agent, price trends |
| Search Locations | `/locations/search` | Location IDs for any city, community or tower |
| Search Properties | `/properties/search` | 25 listings per page with 18 filters and 8 sort orders |
| Price Trends | `/properties/price-trends` | Price per sqft over 1, 2 and 5 years |
| Search Transactions | `/transactions/search` | Dubai Land Department sold prices and rents, with a market summary |
| Area Details | `/areas/details` | Area guide: house prices, nearby places, demographics, market stats |
| Area Reviews | `/areas/reviews` | Resident reviews with scores in 7 categories, 20 per page |
| Search Projects | `/projects/search` | New off-plan projects with starting prices and payment plans |
| Project Details | `/projects/details` | Unit floor plans, payment plans, handover date and FAQs |
| Search Developers | `/developers/search` | 960 developers with logos, licences and project counts |
| Developer Details | `/developers/details` | Developer profile: contacts, founding year, projects by phase |
| Search Agents | `/agents/search` | Agents by name, area, language or nationality, with ratings |
| Agent Details | `/agents/details` | Bio, licence, rating breakdown, closed deals and top areas |
| Agent Listings | `/agents/listings` | Every live listing of one agent, 25 per page |
| Search Companies | `/companies/search` | Real estate companies by name or area, with licences and contacts |
| Company Details | `/companies/details` | Licence, email, phone, address, listing and agent counts, awards |
| Company Agents | `/companies/agents` | Every agent at one company, 20 per page |
| Company Listings | `/companies/listings` | Every live listing of one company, 25 per page |

## 🔍 Exploring Parameters

The same API is published on RapidAPI, and its playground is the easiest place to try parameters and see raw responses. Once a request looks right, run it locally for **unlimited free** data.

1. [Subscribe to the free plan](https://rapidapi.com/OmkarCloud/api/best-property-finder-scraper-free-1000-calls/pricing) — 1,000 calls/month, no credit card.
2. [Try the endpoints in the playground](https://rapidapi.com/OmkarCloud/api/best-property-finder-scraper-free-1000-calls/playground) — every param is pre-filled, so you see real data in one click.
3. Copy the generated code and replace `https://best-property-finder-scraper-free-1000-calls.p.rapidapi.com` with `http://localhost:8000`. It will now run against your local API.

```python
import requests

# generated by the playground, host swapped for the local API
response = requests.get(
    "http://localhost:8000/properties/details",
    params={"property": "167877493"},
)
print(response.json())
```

## 💬 Have Questions? We Have Answers.

You're a developer — we know how hard completing a project can be. So we offer full support: just message us and we'll reply ✅ with a solution within 1 working day.

[![Message Us on WhatsApp about Property Finder Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/whatsapp-us.png)](https://www.omkar.cloud/l/property-finder-scraper-github-whatsapp)

[![Ask Us by Email about Property Finder Scraper](https://raw.githubusercontent.com/omkarcloud/assets/master/images/ask-on-email.png)](mailto:happy.to.help@omkar.cloud?subject=Help%20with%20Property%20Finder%20Scraper%20API&body=I%20need%20help%20using%20the%20Property%20Finder%20Scraper%20API.)

## ⚡ Popular Scrapers by Omkar Cloud

- [**Google Maps Scraper (3,100+ GitHub Stars)**](https://github.com/omkarcloud/google-maps-scraper) — type "dentists in New York", get every business as a ready-to-call lead list: phones, emails, websites & reviews. Up to 100K free leads/month.
- [**G2 Scraper**](https://www.omkar.cloud/tools/g2-scraper) — G2 product details, ratings & AI-found contacts
- [**Website Email Contact Scraper**](https://www.omkar.cloud/tools/website-email-contact-scraper) — emails, phones & socials from any website
- [**AliExpress Scraper**](https://www.omkar.cloud/tools/aliexpress-scraper-api) — live product details, SKU variants, stock & shipping
- [**Booking Scraper**](https://www.omkar.cloud/tools/booking-scraper) — Booking.com hotels: prices, ratings, rooms & amenities
- [**Etsy Scraper**](https://www.omkar.cloud/tools/etsy-scraper) — Etsy products: prices, discounts, shops & variations

## ⭐ Love It? [Star It ⭐!](https://github.com/omkarcloud/property-finder-scraper)

Star the repo ⭐ and become my star hero!

It's just 1 click, but it means the world to me.

[![Star us on GitHub](https://raw.githubusercontent.com/omkarcloud/google-maps-scraper/master/screenshots/star-us.png)](https://github.com/omkarcloud/property-finder-scraper)
