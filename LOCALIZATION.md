# Wood Factory Arabic / English Localization

Wood Factory is bilingual. English remains the source language in code and metadata, while Arabic is supplied through the standard Frappe translation file:

```text
wood_factory/translations/ar.csv
```

This keeps one set of DocTypes and workflows. The visible language changes according to the selected Frappe language; there is no duplicated Arabic database schema or separate Arabic application.

## Approved terminology

| English source | Approved Arabic term |
| --- | --- |
| Wood Factory | إدارة معمل الخشب والألمنيوم |
| Factory Order | أمر تشغيل المعمل |
| Cutting Order | أمر القص |
| Board Layout | مخطط اللوح |
| Factory Piece | قطعة المعمل |
| Piece Exception | استثناء قطعة |
| Board Remnant | فضلة لوح |
| Factory Workstation | محطة عمل المعمل |
| Cutting | القص |
| Edge Banding | القشاط |
| Drilling | التخريم |
| Assembly | التجميع |
| Quality Inspection | فحص الجودة |
| Rework | إعادة العمل |
| Packing | التعبئة |
| Ready for Delivery | جاهز للتسليم |
| Customer Billable | قابل للفوترة على العميل |
| Customer Material Consumption | استهلاك مواد طلب العميل |
| Internal Replacement Material | مواد تعويض داخلي |
| Remnant Material Consumption | استهلاك فضلة لوح |
| Remnant Recovery | قيمة فضلة مستردة |
| Factory Error / Rework Cost | تكلفة خطأ المعمل وإعادة العمل |
| Production Bottleneck | عنق زجاجة الإنتاج |
| What-if Simulation | محاكاة ماذا لو |

## Terminology rules

1. Use **أمر تشغيل المعمل** for `Factory Order`; do not alternate between أمر مصنع، طلب مصنع، and أمر إنتاج.
2. Use **أمر القص** for `Cutting Order`.
3. Use **القشاط** for `Edge Banding`, matching the factory terminology used by the business.
4. Use **فضلة لوح** for a reusable `Board Remnant`; use **قصاصات متلفة** only for unusable scrap.
5. Use **قطعة تعويضية** for a replacement piece caused by missing, damaged, or wrong-dimension work.
6. Use **إعادة العمل** for `Rework` and **تكلفة خطأ المعمل** for internal costs that must not be billed to the customer.
7. Keep dimensions, item codes, document names, QR values, and numeric identifiers left-to-right even inside Arabic pages.
8. English source strings remain in code. Do not hard-code Arabic labels in DocType JSON or JavaScript; add or update the Arabic translation instead.
9. Dynamic customer names, item names, free-text notes, and user-entered data are not machine-translated.
10. Avoid using the same English source for two different meanings. For example, `Open` is a status and translates to **مفتوح**, while the navigation action uses `Open Page` and translates to **فتح الصفحة**.

## Selecting the language

Each user can use a different interface language:

- Arabic users select **العربية** in their Frappe user language.
- English users select **English**.
- The administrator may set the default language in System Settings, while individual user language remains the preferred way to support a bilingual team.

When Arabic is selected, Frappe supplies the RTL page direction. Wood Factory also loads:

```text
/assets/wood_factory/css/wood_factory_rtl.css
```

This stylesheet corrects the custom operational pages and preserves left-to-right display for measurements, money, item codes, document IDs, and QR/barcode values.

## Adding a new label

When a new user-facing label, status, action, page title, or report column is introduced:

1. Keep the English source string clear and specific.
2. Add its approved Arabic translation to `wood_factory/translations/ar.csv`.
3. Preserve placeholders such as `{0}`, `%s`, and `%(name)s` exactly.
4. Avoid duplicate source rows.
5. Run the Arabic translation tests.

## Validation

The baseline translation integrity tests are located at:

```text
wood_factory/tests/test_arabic_translations.py
```

They verify:

- a substantial Arabic dictionary exists;
- every row contains Arabic text;
- English source keys are unique;
- critical factory terminology is covered;
- approved terms do not drift;
- formatting placeholders are preserved;
- status/action terms such as `Open` and `Open Page` remain distinct.

## Deployment commands

These commands have not been executed on the target site yet:

```bash
bench --site almadina.horizontechco.com migrate
bench build --app wood_factory
bench --site almadina.horizontechco.com clear-cache
bench --site almadina.horizontechco.com clear-website-cache
```

Then log in once with an Arabic-language user and once with an English-language user to verify both directions before starting the full end-to-end test stage.
