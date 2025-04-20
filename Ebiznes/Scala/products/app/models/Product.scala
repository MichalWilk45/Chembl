package models 

import play.api.libs.json.{Json, OFormat}

case class Product(id: Int, name: String, price: Double)

object Product {
    implicit val format: OFormat[Product]= Json.format[Product] 
}