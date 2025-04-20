package models

import play.api.libs.json.{Json, OFormat}

case class CartItem(id: Int, productId: Int, quantity: Int)

object CartItem {
  implicit val format: OFormat[CartItem] = Json.format[CartItem]
}
