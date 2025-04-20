package controllers

import javax.inject._
import play.api.mvc._
import play.api.libs.json._
import models.Product
import scala.collection.mutable.ListBuffer

@Singleton
class ProductController @Inject()(cc: ControllerComponents) extends AbstractController(cc) {

  // Lista produktów jako prosta baza danych
  private val products = ListBuffer(
    Product(1, "Laptop", 3000.0),
    Product(2, "Smartphone", 2000.0)
  )

  // Pobranie wszystkich produktów
  def getAll: Action[AnyContent] = Action {
    Ok(Json.toJson(products))
  }

  // Pobranie produktu po ID
  def getById(id: Int): Action[AnyContent] = Action {
    products.find(_.id == id) match {
      case Some(product) => Ok(Json.toJson(product))
      case None => NotFound(Json.obj("error" -> "Product not found"))
    }
  }

  // Dodanie nowego produktu
  def add: Action[JsValue] = Action(parse.json) { request =>
    request.body.validate[Product] match {
      case JsSuccess(newProduct, _) =>
        products += newProduct
        Created(Json.toJson(newProduct))
      case JsError(errors) =>
        BadRequest(Json.obj("error" -> "Invalid JSON", "details" -> JsError.toJson(errors)))
    }
  }

  // Aktualizacja istniejącego produktu
  def update(id: Int): Action[JsValue] = Action(parse.json) { request =>
    request.body.validate[Product] match {
      case JsSuccess(updatedProduct, _) =>
        products.indexWhere(_.id == id) match {
          case -1 => NotFound(Json.obj("error" -> "Product not found"))
          case index =>
            products.update(index, updatedProduct)
            Ok(Json.toJson(updatedProduct))
        }
      case JsError(errors) =>
        BadRequest(Json.obj("error" -> "Invalid JSON", "details" -> JsError.toJson(errors)))
    }
  }

  // Usunięcie produktu po ID
  def delete(id: Int): Action[AnyContent] = Action {
    products.indexWhere(_.id == id) match {
      case -1 => NotFound(Json.obj("error" -> "Product not found"))
      case index =>
        products.remove(index)
        NoContent
    }
  }
}
