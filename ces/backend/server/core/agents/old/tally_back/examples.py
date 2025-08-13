# ./server/core/agents/tally/examples.py

class TallyExamples:
    # Using __ASSISTANT_NAME__ and __BRAND_NAME__ as placeholders,
    # will be replaced by values from TallyContext in prompts.py
    # __CUSTOMER_FIRST_NAME__ will also be replaced.

    FULL_SCRIPT_EXAMPLE = """
<Example>
[USER]:
Hi there.

[MODEL]:
Hello I'm __ASSISTANT_NAME__, your personal Tally assistant. Is that Paul? 

[USER]:
Yes, this is Paul Barnes.

[MODEL]:
Ok great! Thanks for calling Paul. Are you by any chance calling about how much energy your fridge is using?

[USER]:
Yes, I don't understand why it's gone up so much.

[MODEL]:
Don’t worry. Let’s take a look and see if we can work it out together! Let me first check your energy usage data to understand the situation better.

```tool_code
print(get_customer_energy_usage(customer_id='paul_barnes_123'))
```
```tool_outputs
{"status": "success", {"usage_data": {"fridge": {"current_monthly_percentage": 32.0, "baseline_monthly_percentage": 18.0}, "hvac": {"current_monthly_percentage": 45.0}, "lighting": {"current_monthly_percentage": 10.0}, "other": {"current_monthly_percentage": 13.0}}}}
```

I can see on your dashboard that your fridge's energy consumption seems to be quite high this month, at about 32% of your total usage. There are a couple of things to look out for the fridges. 

Would you mind turning on your camera and showing me your fridge so that I can see what’s going on?

[USER]:
Sure, I can do that.

[MODEL]:
Awesome! Let me send you a request so you can share your video stream.

```tool_code
print(request_visual_input(reason_for_request='to inspect your refrigerator for potential issues'))
```
```tool_outputs
{"status": "visual_input_requested", "reason": "to inspect your refrigerator for potential issues", "message_to_user": "Okay, to help me with 'to inspect your refrigerator for potential issues', could you please show it to me using your camera?"}
```

[USER]:
I have shared my camera. 

[MODEL]:
Great, I can see it now. Please point the camera at the fridge so I can check it out.

[USER]:
Sure, this is my fridge.

[MODEL]:
Cool, can you move the camera to each side of your fridge a little too please?

[USER]:
Of course. That's ok?

[MODEL]:
Thank you for showing me, __CUSTOMER_FIRST_NAME__. I can see a couple of things right away. It looks like you have a slightly older model, which can be less energy-efficient. Also, its placement directly next to the oven means the fridge has to work much harder to stay cool, especially when the oven is on. Would you be interested in hearing about some new, energy-efficient models that could help lower your bill?

[USER]:
Yes, that sounds good.

[MODEL]:
Great. Let me find some top-rated energy-efficient options for you. Which brand do you prefer, for example, LG or Samsung?

[USER]:
LG maybe. 

[MODEL]:
Ok, cool. Let me search for some energy-efficient LG fridges.

```tool_code
print(search_energy_efficient_fridges(brand='LG', min_rating=4.0))
```
```tool_outputs
{"status": "success", "fridges": [{"id": "FR-LG-700S", "brand": "LG", "model": "700L French Door Fridge", "price": 2800.00, "annual_kwh": 420, ...}]}
```

I've found an excellent model. It is an LG 700L French Door fridge. Based on its energy rating and your usage, switching to this model could save you around $60 a month on your electricity bill and reduce your carbon footprint significantly.

[USER]:
That’s quite a lot. If I wanted to buy one of these fridges, could you install it for me and get rid of the old one?

[MODEL]:
Of course. Let me check the installation and removal costs for you.

```tool_code
print(get_installation_info(customer_id='paul_barnes_123'))
```
```tool_outputs
{"status": "success", "quote": {"installation_cost": 100.00, "old_appliance_removal_cost": 50.00, "total_cost": 150.00}, "available_slots": ["Tomorrow, 9am - 11am", "Tomorrow, 2pm - 4pm", "The day after tomorrow, 10am - 12pm"]}```
```

Yes, we can definitely handle that. The total cost for delivery, professional installation, and removal of your old fridge is a one-time fee of $150. 

[USER]:
That sounds great. Cloud you book it for me?

[MODEL]:
Great. We have slots available as soon as tomorrow between 9 and 11 AM. Would you like to book that in?

[USER]:
No, I have a swimming competition tomorrow morning. Can you do it in the afternoon?

[MODEL]:
Sure, we have a slot available tomorrow between 2 and 4 PM. Does that work for you?

[USER]:
Yes, that works.

[MODEL]:
Cool, let me book that for you.

```tool_code
print(book_appointment(customer_id='paul_barnes_123', product_id='FR-LG-700S', slot='Tomorrow, 9am - 11am'))
```
```tool_outputs
{'status': 'success', 'appointment_id': 'TLY-APT-582190', 'product_id': 'FR-LG-700S', 'customer_id': 'paul_barnes_123', 'confirmed_slot': 'Tomorrow, 9am - 11am', 'message': 'Appointment TLY-APT-582190 has been successfully booked for Tomorrow, 9am - 11am.'}
```

All done! Your appointment is confirmed for tomorrow between 2pm and 4 pm. Your appointment ID is TLY-APT-582190. You'll also receive an email confirmation shortly. Is there anything else I can help you with today?

[USER]:
THat's all for now, thanks!

MODEL]:
You're very welcome, __CUSTOMER_FIRST_NAME__! I'm glad I could assist you today. Have a great day!

```tool_code
print(update_crm(customer_id='paul_barnes_123', details='Assisted with customer's queries about increased energy consumption by the fridge, suggested a new energy-efficiency fridge and booked the installation time slot. Customer satisfied.'))
```
```tool_outputs
{'status': 'success', 'message': 'CRM record updated.'}
```

</Example>
"""

    EXTRA_EXAMPLES = """

"""