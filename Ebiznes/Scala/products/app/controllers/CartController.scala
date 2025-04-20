package controllers

import javax.inject._
import play.api.mvc._
import play.api.libs.json._
import models.CartItem
import scala.collection.mutable.ListBuffer

@Singleton
class CartController @Inject()(cc: ControllerComponents) extends AbstractController(cc) {

  // Koszyk jako lista produktów
  private val cart = ListBuffer(
    CartItem(1, productId = 1, quantity = 2),
    CartItem(2, productId = 2, quantity = 1)
  )

  def getAll: Action[AnyContent] = Action {
    Ok(Json.toJson(cart))
  }

  def getById(id: Int): Action[AnyContent] = Action {
    cart.find(_.id == id) match {
      case Some(cartItem) => Ok(Json.toJson(cartItem))
      case None => NotFound(Json.obj("error" -> "Cart item not found"))
    }
  }

  def add: Action[JsValue] = Action(parse.json) { request =>
    request.body.validate[CartItem] match {
      case JsSuccess(newItem, _) =>
        cart += newItem
        Created(Json.toJson(newItem))
      case JsError(errors) =>
        BadRequest(Json.obj("error" -> "Invalid JSON", "details" -> JsError.toJson(errors)))
    }
  }

  def update(id: Int): Action[JsValue] = Action(parse.json) { request =>
    request.body.validate[CartItem] match {
      case JsSuccess(updatedItem, _) =>
        cart.indexWhere(_.id == id) match {
          case -1 => NotFound(Json.obj("error" -> "Cart item not found"))
          case index =>
            cart.update(index, updatedItem)
            Ok(Json.toJson(updatedItem))
        }
      case JsError(errors) =>
        BadRequest(Json.obj("error" -> "Invalid JSON", "details" -> JsError.toJson(errors)))
    }
  }

  def delete(id: Int): Action[AnyContent] = Action {
    cart.indexWhere(_.id == id) match {
      case -1 => NotFound(Json.obj("error" -> "Cart item not found"))
      case index =>
        cart.remove(index)
        NoContent
    }
  }
}
