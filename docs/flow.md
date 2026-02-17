# Support Flow: client_v1

## block: start
type: message
text: "Привет! Я бот поддержки. Сейчас покажу доступные разделы."
rules:
  hide_on_next: true
next: main_menu

---

## block: main_menu
type: menu
menu_id: main
text: "Выберите тему:"
rules:
  hide_on_next: false
  replace_menu: true
buttons:
  - id: billing
    text: "Оплата"
    next: billing
  - id: delivery
    text: "Доставка"
    next: delivery
  - id: operator
    text: "Оператор"
    next: end

---

## block: billing
type: mes-menu
text: "По оплате: проверьте статус платежа в личном кабинете. Если не помогло, напишите оператору."
rules:
  hide_on_next: true
button:
  id: billing_back
  text: "Назад в меню"
  next: main_menu

---

## block: delivery
type: mes-menu
text: "По доставке: пришлите номер заказа оператору, и он проверит статус."
rules:
  hide_on_next: true
button:
  id: delivery_back
  text: "Назад в меню"
  next: main_menu

---

## block: end
type: message
text: "Передаю ваш запрос оператору. Ответ придет в ближайшее время."
rules:
  hide_on_next: false
